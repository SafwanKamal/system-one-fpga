// SPDX-License-Identifier: GPL-2.0-only
/* Fixed KR260 TCMA smoke controller. Loading is passive; no remoteproc/overlay.
 * This diagnostic build permits one fixed, TCM-only image and timed recovery.
 * No user-supplied firmware, physical address, register or PM node is accepted.
 */
#include <linux/arm-smccc.h>
#include <linux/capability.h>
#include <linux/clk.h>
#include <linux/delay.h>
#include <linux/firmware/xlnx-zynqmp.h>
#include <linux/fs.h>
#include <linux/io.h>
#include <linux/ioport.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/slab.h>
#include <linux/suspend.h>
#include <linux/workqueue.h>
#include "session.h"
#include "smoke_image.h"

#define TCMA_PA 0xffe00000ULL
#define TCMA_SIZE 0x10000U
#define RPU0 7U
#define RPU1 8U
#define TCMA0 15U
#define TCMA1 17U
#define TRACE_OFFSET 0x1000U
#define TRACE_SIZE 128U
#define RECOVERY_MS 5000U
/* Change only in a new, independently reviewed build after hardware gates. */
#define SYSONE_R5_LIVE_ADMITTED 1
#define SYSONE_R5_PREPARE_ADMITTED 1

static DEFINE_MUTEX(smoke_lock);
static struct resource *tcma_resource;
static struct clk *probe_clock;
static void __iomem *tcma;
static char saved_trace[TRACE_SIZE+1];
static unsigned int audit_mode, audit_r0, audit_r1, audit_usage, audit_usage1;
static int audit_result = -ENODATA;
static bool initialized;
static struct smoke_session session;
static void recover_workfn(struct work_struct *work);
static DECLARE_DELAYED_WORK(recover_work, recover_workfn);

static int smoke_pm_event(struct notifier_block *nb, unsigned long event, void *unused)
{
	int ret = NOTIFY_OK;
	if (event == PM_SUSPEND_PREPARE || event == PM_HIBERNATION_PREPARE ||
	    event == PM_RESTORE_PREPARE) {
		mutex_lock(&smoke_lock);
		if (session.pinned)
			ret = NOTIFY_BAD;
		mutex_unlock(&smoke_lock);
	}
	return ret;
}
static struct notifier_block smoke_pm_notifier = {.notifier_call=smoke_pm_event};

/* Only GET_RPU_OPER_MODE; direct returned register, no caller response array.
 * Exact advertised ATF ABI: a0[31:0]=status, a0[63:32]=mode. The kernel's
 * exported getter uses the wrong slot on 6.8.0-1036; never call that getter.
 */
static int correct_mode(unsigned int *mode)
{
	struct arm_smccc_res result;
	u32 status;

	arm_smccc_smc(PM_SIP_SVC | PM_IOCTL, RPU0, 0, 0, 0, 0, 0, 0, &result);
	status = lower_32_bits(result.a0);
	if (status)
		return -EIO;
	*mode = upper_32_bits(result.a0);
	return *mode <= 1 ? 0 : -EPROTO;
}

static int smoke_node_state(u32 node, u32 *state, u32 *usage)
{
	/* Initialize even on firmware errors; the kernel helper only fills on
	 * firmware success and has a correctly sized local response buffer.
	 */
	*state = ~0U;
	if (usage)
		*usage = ~0U;
	return zynqmp_pm_get_node_status(node, state, NULL, usage);
}

static int no_rpu_dt_owner(void)
{
	struct device_node *node;
	const char * const compatibles[] = {
		"xlnx,zynqmp-r5-remoteproc", "xlnx,zynqmp-r5fss", "xilinx,r5f"
	};
	unsigned int i;
	for (i = 0; i < ARRAY_SIZE(compatibles); i++) {
		for_each_compatible_node(node, NULL, compatibles[i]) {
			if (of_device_is_available(node)) {
				of_node_put(node);
				return -EBUSY;
			}
		}
	}
	return 0;
}

static int inspect(void *ctx)
{
	u32 state, usage;
	int ret;

	ret = no_rpu_dt_owner();
	if (ret)
		return ret;
	ret = correct_mode(&audit_mode);
	if (ret)
		return ret;
	ret = smoke_node_state(RPU0, &audit_r0, NULL);
	if (ret)
		return ret;
	ret = smoke_node_state(RPU1, &audit_r1, NULL);
	if (ret)
		return ret;
	ret = smoke_node_state(TCMA0, &state, &usage);
	if (ret)
		return ret;
	audit_usage = usage;
	ret = smoke_node_state(TCMA1, &state, &audit_usage1);
	if (ret)
		return ret;
	/* No mode/config writes. Claim both ATCM banks, use only low 64KiB.
	 * RPU status 0 is FORCEDOFF. SLEEP is not a reset-entry proof.
	 */
	return audit_mode <= 1 && audit_r0 == 0 && audit_r1 == 0 &&
	       usage == PM_USAGE_NO_MASTER && audit_usage1 == PM_USAGE_NO_MASTER ? 0 : -EBUSY;
}

static int pin(void *ctx) { return try_module_get(THIS_MODULE) ? 0 : -ENODEV; }
static void unpin(void *ctx) { module_put(THIS_MODULE); }
static int reserve(void *ctx)
{
	struct device_node *node;
	struct resource range;
	int ret;
	tcma_resource = request_mem_region(TCMA_PA, TCMA_SIZE, "sysone-r5-smoke");
	if (!tcma_resource)
		return -EBUSY;
	node = of_find_compatible_node(NULL, NULL, "sysone,axi-origin-probe-v1");
	if (!node) {
		ret = -ENODEV;
		goto release_tcm;
	}
	ret = of_address_to_resource(node, 0, &range);
	if (ret || !of_device_is_available(node) || range.start != 0xa0000000ULL ||
	    resource_size(&range) != 4096) {
		of_node_put(node);
		ret = ret ? ret : -EINVAL;
		goto release_tcm;
	}
	probe_clock = of_clk_get(node, 0);
	of_node_put(node);
	if (IS_ERR(probe_clock)) {
		ret = PTR_ERR(probe_clock);
		probe_clock = NULL;
		goto release_tcm;
	}
	if (clk_get_rate(probe_clock) <= 95000000 || clk_get_rate(probe_clock) > 100000000) {
		ret = -ERANGE;
		goto put_clock;
	}
	ret = clk_prepare_enable(probe_clock);
	if (ret)
		goto put_clock;
	return 0;
put_clock:
	clk_put(probe_clock);
	probe_clock = NULL;
release_tcm:
	release_mem_region(TCMA_PA, TCMA_SIZE);
	tcma_resource = NULL;
	return ret;
}
static void unreserve(void *ctx)
{
	/* The session engine reaches this only after stopped confirmation and
	 * both TCM leases are released; quarantine retains the clock reference.
	 */
	clk_disable_unprepare(probe_clock);
	clk_put(probe_clock);
	probe_clock = NULL;
	release_mem_region(TCMA_PA, TCMA_SIZE);
	tcma_resource = NULL;
}
static int request(void *ctx, unsigned int bank)
{
	return zynqmp_pm_request_node(bank ? TCMA1 : TCMA0, ZYNQMP_PM_CAPABILITY_ACCESS, 0,
				      ZYNQMP_PM_REQUEST_ACK_BLOCKING);
}
static int lease(void *ctx, unsigned int bank)
{
	u32 state, usage;
	int ret = smoke_node_state(bank ? TCMA1 : TCMA0, &state, &usage);
	if (ret)
		return ret;
	if (usage == PM_USAGE_NO_MASTER)
		return 0;
	if (usage == PM_USAGE_CURRENT_MASTER)
		return 1;
	return -EBUSY;
}
static int release(void *ctx, unsigned int bank)
{
	return zynqmp_pm_release_node(bank ? TCMA1 : TCMA0);
}
static int stop(void *ctx)
{
	return zynqmp_pm_force_pwrdwn(RPU0, ZYNQMP_PM_REQUEST_ACK_BLOCKING);
}
static int off(void *ctx)
{
	u32 state;
	int ret = smoke_node_state(RPU0, &state, NULL);
	return ret ? ret : state == 0 ? 0 : -EBUSY;
}
static int map(void *ctx)
{
	tcma = ioremap(TCMA_PA, TCMA_SIZE);
	return tcma ? 0 : -ENOMEM;
}
static void unmap(void *ctx)
{
	iounmap(tcma);
	tcma = NULL;
	initialized = false;
}
static int load(void *ctx)
{
	u32 offset;
	u64 expected;
	/* Full aligned doubleword stores, including unused bytes, before reads.
	 * Hardware ECC/access/power sequencing must still be qualified separately.
	 */
	initialized = false;
	memset(saved_trace, 0, sizeof(saved_trace));
	for (offset = 0; offset < TCMA_SIZE; offset += 8) {
		expected = offset < sizeof(smoke_image) ? smoke_image[offset/8] : 0;
		writeq(expected, tcma + offset);
	}
	wmb();
	for (offset = 0; offset < TCMA_SIZE; offset += 8) {
		expected = offset < sizeof(smoke_image) ? smoke_image[offset/8] : 0;
		if (readq(tcma + offset) != expected)
			return -EIO;
	}
	initialized = true;
	return 0;
}
static int wake(void *ctx)
{
	/* Keep vendor NOACK wake semantics; success is only submission. The
	 * independently scheduled recovery and fresh trace determine the outcome.
	 */
	return zynqmp_pm_request_wake(RPU0, true, PM_RPU_BOOTMEM_LOVEC,
				      ZYNQMP_PM_REQUEST_ACK_NO);
}
static const struct smoke_ops ops = {
	pin, unpin, reserve, unreserve, inspect, request, lease, release,
	stop, off, map, unmap, load, wake
};

static void capture_trace(void)
{
	unsigned int i;
	if (!tcma || !initialized)
		return;
	for (i = 0; i < TRACE_SIZE; i += 4) {
		u32 word = readl(tcma + TRACE_OFFSET + i);
		memcpy(saved_trace+i, &word, sizeof(word));
	}
	saved_trace[TRACE_SIZE] = 0;
}
static void recover_workfn(struct work_struct *work)
{
	int ret;
	mutex_lock(&smoke_lock);
	capture_trace();
	ret = smoke_recover(&session);
	pr_info("sysone_r5_smoke: bounded recovery ret=%d quarantine=%d\n",
		ret, session.quarantined);
	mutex_unlock(&smoke_lock);
}
static ssize_t status_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	ssize_t len;
	mutex_lock(&smoke_lock);
	len = sysfs_emit(buf, "pinned=%d reserved=%d lease_pending=%d mapped=%d may_run=%d loaded=%d quarantine=%d error=%d recovery_error=%d audit=%d mode=%u r0=%u r1=%u usage=%u usage1=%u live_enabled=%d prepare_enabled=%d image_sha256=%s\n",
		session.pinned, session.reserved, session.lease_pending, session.mapped,
		session.may_run, session.loaded, session.quarantined, session.last_error,
		session.recovery_error, audit_result, audit_mode, audit_r0, audit_r1,
		audit_usage, audit_usage1, SYSONE_R5_LIVE_ADMITTED, SYSONE_R5_PREPARE_ADMITTED, SMOKE_ELF_SHA256);
	mutex_unlock(&smoke_lock);
	return len;
}
static ssize_t trace_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	ssize_t len;
	mutex_lock(&smoke_lock);
	capture_trace();
	len = sysfs_emit(buf, "%.*s", TRACE_SIZE, saved_trace);
	mutex_unlock(&smoke_lock);
	return len;
}
static ssize_t command_store(struct device *dev, struct device_attribute *attr,
			     const char *buf, size_t count)
{
	int ret;
	if (!capable(CAP_SYS_RAWIO))
		return -EPERM;
	mutex_lock(&smoke_lock);
	if (sysfs_streq(buf, "audit")) {
		if (session.pinned)
			ret = -EBUSY;
		else
			ret = audit_result = inspect(NULL);
	} else if (sysfs_streq(buf, "stop")) {
		/* Work may be queued; mutex serializes it and recovery is idempotent. */
		capture_trace();
		ret = smoke_recover(&session);
	} else if (sysfs_streq(buf, "prepare")) {
		/* Arm recovery before the first possible firmware mutation. */
		if (!SYSONE_R5_PREPARE_ADMITTED) {
			ret = -EOPNOTSUPP;
		} else if (session.pinned || session.quarantined) {
			ret = -EBUSY;
		} else {
			mod_delayed_work(system_wq, &recover_work, msecs_to_jiffies(RECOVERY_MS));
			ret = smoke_prepare(&session);
		}
	} else if (sysfs_streq(buf, "start")) {
		if (!SYSONE_R5_LIVE_ADMITTED) {
			ret = -EOPNOTSUPP;
		} else if (!session.loaded || session.may_run || session.quarantined) {
			ret = -EINVAL;
		} else {
			mod_delayed_work(system_wq, &recover_work, msecs_to_jiffies(RECOVERY_MS));
			ret = smoke_start(&session);
		}
	} else {
		ret = -EINVAL;
	}
	mutex_unlock(&smoke_lock);
	return ret ? ret : (ssize_t)count;
}
static DEVICE_ATTR_RO(status);
static DEVICE_ATTR_WO(command);
static struct device_attribute dev_attr_trace = __ATTR(trace, 0400, trace_show, NULL);
static struct attribute *smoke_attrs[] = {
	&dev_attr_status.attr, &dev_attr_command.attr, &dev_attr_trace.attr, NULL
};
ATTRIBUTE_GROUPS(smoke);
static const struct file_operations smoke_fops = {.owner=THIS_MODULE, .llseek=no_llseek};
static struct miscdevice smoke_dev = {
	.minor=MISC_DYNAMIC_MINOR, .name="sysone_r5_smoke", .fops=&smoke_fops,
	.groups=smoke_groups, .mode=0600
};
static int __init smoke_init(void)
{
	struct device_node *fw;
	const char *method;
	int ret;
	if (!of_machine_is_compatible("xlnx,zynqmp-sk-kr260-revB"))
		return -ENODEV;
	fw = of_find_compatible_node(NULL, NULL, "xlnx,zynqmp-firmware");
	if (!fw)
		return -ENODEV;
	ret = of_property_read_string(fw, "method", &method);
	if (!ret && strcmp(method, "smc"))
		ret = -EOPNOTSUPP;
	of_node_put(fw);
	if (ret)
		return ret;
	session.ops = &ops;
	ret = register_pm_notifier(&smoke_pm_notifier);
	if (ret)
		return ret;
	ret = misc_register(&smoke_dev);
	if (ret)
		unregister_pm_notifier(&smoke_pm_notifier);
	return ret;
}
static void __exit smoke_exit(void)
{
	misc_deregister(&smoke_dev);
	cancel_delayed_work_sync(&recover_work);
	unregister_pm_notifier(&smoke_pm_notifier);
	/* Any unresolved session holds THIS_MODULE and prevents ordinary unload. */
	WARN_ON(session.pinned || session.mapped || session.lease_pending);
}
module_init(smoke_init);
module_exit(smoke_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("KR260 TCM R5 AXI-origin diagnostic; fixed PL aperture and image");
