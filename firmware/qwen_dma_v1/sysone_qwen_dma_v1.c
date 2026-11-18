// Owned scatter DMA model storage for a Linux-live FPGA decoder.
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/dma-mapping.h>
#include <linux/miscdevice.h>
#include <linux/fs.h>
#include <linux/mm.h>
#include <linux/overflow.h>

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

static int owned_mmap(struct file *file, struct vm_area_struct *vma)
{
    unsigned long page_offset = vma->vm_pgoff;
    unsigned long index = page_offset / (SEGMENT_BYTES >> PAGE_SHIFT);
    unsigned long remainder = page_offset % (SEGMENT_BYTES >> PAGE_SHIFT);
    unsigned long bytes = vma->vm_end - vma->vm_start;
    if (remainder || index >= count || bytes > segments[index].bytes)
        return -EINVAL;
    vma->vm_pgoff = 0;
    vm_flags_set(vma, VM_DONTEXPAND | VM_DONTDUMP);
    return dma_mmap_coherent(&owner->dev, vma, segments[index].cpu,
                             segments[index].dma, segments[index].bytes);
}
static long owned_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    if (cmd != SYNC_COMMAND) return -ENOTTY;
    dma_wmb();
    return 0;
}
static const struct file_operations owned_fops = {
    .owner=THIS_MODULE, .mmap=owned_mmap, .unlocked_ioctl=owned_ioctl,
    .llseek=no_llseek,
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
    if(!remaining || remaining > MAX_SEGMENTS*SEGMENT_BYTES)return -EINVAL;
    owner=platform_device_register_simple("sysone_qwen_dma_v1",-1,NULL,0);
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
MODULE_DESCRIPTION("Linux-owned DMA storage for Qwen FPGA weights; no arbitrary RAM reservation");
