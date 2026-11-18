// Owned scatter DMA model storage for a Linux-live FPGA decoder.
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/dma-mapping.h>
#include <linux/miscdevice.h>
#include <linux/fs.h>
#include <linux/mm.h>
#include <linux/overflow.h>
#include <linux/mutex.h>
#include <linux/random.h>
#include <linux/capability.h>
#include <linux/sched.h>
#include <linux/slab.h>
#include <linux/refcount.h>

#define SEGMENT_BYTES (16UL << 20)
#define MAX_SEGMENTS 64
#define SYNC_COMMAND 0x515701
struct segment { void *cpu; dma_addr_t dma; size_t bytes; };
static struct segment segments[MAX_SEGMENTS];
static unsigned int count;
static unsigned long model_bytes = 639446688;
module_param(model_bytes, ulong, 0444);
MODULE_PARM_DESC(model_bytes,"Exact immutable GGUF file extent, at most 1GiB");
static struct platform_device *owner;

/* Each open owns the whole model. VMA references pin that file/module. */
#define BEGIN_LOAD 0x515702
#define SEAL_MODEL 0x515703
#define CLAIM_INFERENCE 0x515704
static DEFINE_MUTEX(ownership_lock);
static bool opened, loading, sealed;
static atomic_t live_vmas = ATOMIC_INIT(0);
static u64 instance, generation;
static pid_t owner_tgid;
struct owner_context { bool inference; };

static int owned_open(struct inode *inode, struct file *file)
{
    struct owner_context *ctx;
    int ret = 0;
    ctx = kzalloc(sizeof(*ctx), GFP_KERNEL);
    if (!ctx) return -ENOMEM;
    mutex_lock(&ownership_lock);
    if (opened) ret = -EBUSY;
    else { opened = true; owner_tgid = task_tgid_nr(current); file->private_data = ctx; }
    mutex_unlock(&ownership_lock);
    if (ret) kfree(ctx);
    return ret;
}
static int owned_release(struct inode *inode, struct file *file)
{
    mutex_lock(&ownership_lock);
    /* Incomplete loads stay unsealed; nobody may infer from them. */
    loading = false; opened = false; owner_tgid = 0;
    mutex_unlock(&ownership_lock);
    kfree(file->private_data);
    return 0;
}
/* Copy callbacks without replacing vm_private_data used by the DMA backend. */
struct mapping_ops {
    struct vm_operations_struct ops;
    const struct vm_operations_struct *original;
    refcount_t references;
};
static void owned_vma_open(struct vm_area_struct *vma)
{
    struct mapping_ops *tracked = container_of(vma->vm_ops, struct mapping_ops, ops);
    refcount_inc(&tracked->references);
    atomic_inc(&live_vmas);
    if (tracked->original && tracked->original->open) tracked->original->open(vma);
}
static void owned_vma_close(struct vm_area_struct *vma)
{
    struct mapping_ops *tracked = container_of(vma->vm_ops, struct mapping_ops, ops);
    if (tracked->original && tracked->original->close) tracked->original->close(vma);
    atomic_dec(&live_vmas);
    if (refcount_dec_and_test(&tracked->references)) kfree(tracked);
}
static int owned_mmap(struct file *file, struct vm_area_struct *vma)
{
    struct owner_context *ctx = file->private_data;
    unsigned long page_offset = vma->vm_pgoff;
    unsigned long index = page_offset / (SEGMENT_BYTES >> PAGE_SHIFT);
    unsigned long remainder = page_offset % (SEGMENT_BYTES >> PAGE_SHIFT);
    unsigned long bytes = vma->vm_end - vma->vm_start;
    int ret;
    struct mapping_ops *tracked;
    if (remainder || index >= count || !bytes || bytes > segments[index].bytes)
        return -EINVAL;
    if (!(vma->vm_flags & VM_SHARED)) return -EINVAL;
    mutex_lock(&ownership_lock);
    if (!loading && !sealed) { ret = -EPERM; goto out; }
    if ((vma->vm_flags & VM_WRITE) && (!loading || ctx->inference)) {
        ret = -EPERM; goto out;
    }
    vma->vm_pgoff = 0;
    vm_flags_set(vma, VM_DONTEXPAND | VM_DONTDUMP | VM_DONTCOPY);
    if (!loading || ctx->inference) vm_flags_clear(vma, VM_MAYWRITE);
    tracked = kzalloc(sizeof(*tracked), GFP_KERNEL);
    if (!tracked) { ret = -ENOMEM; goto out; }
    ret = dma_mmap_coherent(&owner->dev, vma, segments[index].cpu,
                           segments[index].dma, segments[index].bytes);
    if (ret) { kfree(tracked); goto out; }
    tracked->original = vma->vm_ops;
    if (vma->vm_ops) tracked->ops = *vma->vm_ops;
    tracked->ops.open = owned_vma_open;
    tracked->ops.close = owned_vma_close;
    refcount_set(&tracked->references, 1);
    vma->vm_ops = &tracked->ops;
    atomic_inc(&live_vmas);
out:
    mutex_unlock(&ownership_lock);
    return ret;
}
static long owned_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    struct owner_context *ctx = file->private_data;
    int ret = 0;
    if (cmd == SYNC_COMMAND) { dma_wmb(); return 0; }
    mutex_lock(&ownership_lock);
    switch (cmd) {
    case BEGIN_LOAD:
        if (ctx->inference || !capable(CAP_SYS_RAWIO)) { ret = -EPERM; break; }
        if (atomic_read(&live_vmas)) { ret = -EBUSY; break; }
        sealed = false; loading = true; generation++;
        break;
    case SEAL_MODEL:
        if (ctx->inference || !loading) { ret = -EPERM; break; }
        if (atomic_read(&live_vmas)) { ret = -EBUSY; break; }
        dma_wmb(); sealed = true; loading = false; generation++;
        break;
    case CLAIM_INFERENCE:
        if (!sealed || loading) { ret = -EPERM; break; }
        if (atomic_read(&live_vmas)) { ret = -EBUSY; break; }
        ctx->inference = true;
        break;
    default: ret = -ENOTTY;
    }
    mutex_unlock(&ownership_lock);
    return ret;
}
static const struct file_operations owned_fops = {
    .owner=THIS_MODULE, .open=owned_open, .release=owned_release,
    .mmap=owned_mmap, .unlocked_ioctl=owned_ioctl, .llseek=no_llseek,
};
static struct miscdevice owned_misc = {
    .minor=MISC_DYNAMIC_MINOR, .name="sysone_qwen_dma", .mode=0600,
    .fops=&owned_fops,
};
static ssize_t buffers_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    ssize_t n=0;unsigned int i;
    n+=sysfs_emit_at(buf,n,"model_bytes=%lu chunk_bytes=%lu segments=%u\n",
                     model_bytes,SEGMENT_BYTES,count);
    for(i=0;i<count;i++)
        n+=sysfs_emit_at(buf,n,"index=%u dma=0x%llx bytes=%zu\n",i,
                         (unsigned long long)segments[i].dma,segments[i].bytes);
    return n;
}
static DEVICE_ATTR_RO(buffers);
static ssize_t ownership_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    ssize_t n;
    mutex_lock(&ownership_lock);
    n = sysfs_emit(buf, "abi=2 instance=%llu generation=%llu sealed=%u loading=%u owner_tgid=%d vmas=%d\n",
                   (unsigned long long)instance, (unsigned long long)generation,
                   sealed, loading, owner_tgid, atomic_read(&live_vmas));
    mutex_unlock(&ownership_lock);
    return n;
}
static DEVICE_ATTR_RO(ownership);
static void release_segments(void)
{
    while(count) {
        struct segment *s=&segments[--count];
        dma_free_coherent(&owner->dev,s->bytes,s->cpu,s->dma);
        s->cpu=NULL;
    }
}
static int __init owned_init(void)
{
    unsigned long remaining=model_bytes;int ret;
    instance = get_random_u64();
    if(!remaining || remaining > MAX_SEGMENTS*SEGMENT_BYTES)return -EINVAL;
    owner=platform_device_register_simple("sysone_qwen_dma_v2",-1,NULL,0);
    if(IS_ERR(owner))return PTR_ERR(owner);
    owner->dev.dma_mask=&owner->dev.coherent_dma_mask;
    ret=dma_set_mask_and_coherent(&owner->dev,DMA_BIT_MASK(32));
    if(ret)goto device_fail;
    while(remaining) {
        struct segment *s=&segments[count];
        unsigned long payload=min(remaining,SEGMENT_BYTES);
        s->bytes=PAGE_ALIGN(payload);
        s->cpu=dma_alloc_coherent(&owner->dev,s->bytes,&s->dma,GFP_KERNEL|__GFP_NOWARN);
        if(!s->cpu){ret=-ENOMEM;goto allocation_fail;}
        count++;
        if((u64)s->dma+s->bytes > 0x80000000ULL) {
            ret=-ERANGE;goto allocation_fail;
        }
        remaining-=payload;
    }
    ret=misc_register(&owned_misc);
    if(ret)goto allocation_fail;
    ret=device_create_file(owned_misc.this_device,&dev_attr_buffers);
    if(ret){misc_deregister(&owned_misc);goto allocation_fail;}
    ret=device_create_file(owned_misc.this_device,&dev_attr_ownership);
    if(ret){device_remove_file(owned_misc.this_device,&dev_attr_buffers);misc_deregister(&owned_misc);goto allocation_fail;}
    pr_info("sysone_qwen_dma: owned %lu model bytes in %u coherent DMA segments\n",model_bytes,count);
    return 0;
allocation_fail:
    release_segments();
device_fail:
    platform_device_unregister(owner);return ret;
}
static void __exit owned_exit(void)
{
    device_remove_file(owned_misc.this_device,&dev_attr_buffers);
    misc_deregister(&owned_misc);release_segments();platform_device_unregister(owner);
}
module_init(owned_init);
module_exit(owned_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Exclusive sealed DMA storage for Qwen FPGA weights; ABI2");
