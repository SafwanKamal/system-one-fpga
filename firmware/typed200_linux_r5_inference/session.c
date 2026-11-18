/* SPDX-License-Identifier: GPL-2.0-only */
#ifdef __KERNEL__
#include <linux/errno.h>
#else
#include <errno.h>
#endif
#include "session.h"

static int smoke_quarantine(struct smoke_session *s, int error)
{
	s->quarantined = 1;
	s->recovery_error = error;
	return error;
}

int smoke_recover(struct smoke_session *s)
{
	int ret;
	int bank;

	/* Stop and independently query OFF before releasing anything R5 can use.
	 * A failed stop is never interpreted as a successful offline transition.
	 */
	if (s->may_run) {
		ret = s->ops->stop(s->ctx);
		if (ret)
			return smoke_quarantine(s, ret);
		ret = s->ops->off(s->ctx);
		if (ret)
			return smoke_quarantine(s, ret);
		s->may_run = 0;
	}
	if (s->mapped) {
		s->ops->unmap(s->ctx);
		s->mapped = 0;
	}
	s->loaded = 0;
	for (bank = 1; bank >= 0; bank--) {
		if (!(s->lease_pending & (1 << bank)))
			continue;
		/* Reconcile even a failed request: firmware may have acquired it
		 * before a transport/error response. Never release someone else's.
		 */
		ret = s->ops->lease(s->ctx, bank);
		if (ret != 0 && ret != 1)
			return smoke_quarantine(s, ret < 0 ? ret : -EIO);
		if (ret == 1) {
			ret = s->ops->release(s->ctx, bank);
			/* Keep pending ownership on ALL release errors. A later recovery
			 * queries again and avoids double release if it already took effect.
			 */
			if (ret)
				return smoke_quarantine(s, ret);
			ret = s->ops->lease(s->ctx, bank);
			if (ret != 0)
				return smoke_quarantine(s, ret < 0 ? ret : -EBUSY);
		}
		s->lease_pending &= ~(1 << bank);
	}
	if (s->reserved) {
		s->ops->unreserve(s->ctx);
		s->reserved = 0;
	}
	if (s->pinned) {
		s->ops->unpin(s->ctx);
		s->pinned = 0;
	}
	s->quarantined = 0;
	s->recovery_error = 0;
	return 0;
}

int smoke_prepare(struct smoke_session *s)
{
	int ret;
	unsigned int bank;

	if (s->pinned || s->quarantined)
		return -EBUSY;
	s->last_error = 0;
	ret = s->ops->pin(s->ctx);
	if (ret)
		return ret;
	s->pinned = 1;
	ret = s->ops->reserve(s->ctx);
	if (ret)
		goto fail;
	s->reserved = 1;
	ret = s->ops->inspect(s->ctx);
	if (ret)
		goto fail;
	/* From this point a request can have side effects even if it errors. */
	s->may_run = 1;
	for (bank = 0; bank < 2; bank++) {
		s->lease_pending |= 1 << bank;
		ret = s->ops->request(s->ctx, bank);
		if (ret)
			goto fail;
		ret = s->ops->lease(s->ctx, bank);
		if (ret != 1) {
			ret = ret < 0 ? ret : -EACCES;
			goto fail;
		}
	}
	ret = s->ops->stop(s->ctx);
	if (ret)
		goto fail;
	s->may_run = 1;
	ret = s->ops->off(s->ctx);
	if (ret)
		goto fail;
	s->may_run = 0;
	ret = s->ops->map(s->ctx);
	if (ret)
		goto fail;
	s->mapped = 1;
	ret = s->ops->load(s->ctx);
	if (ret)
		goto fail;
	s->loaded = 1;
	return 0;
fail:
	s->last_error = ret;
	smoke_recover(s);
	return ret;
}

int smoke_start(struct smoke_session *s)
{
	int ret;

	if (!s->loaded || !s->mapped || s->lease_pending != 3 ||
	    s->may_run || s->quarantined)
		return -EINVAL;
	/* Revalidate immediately before wake. No cleanup may assume an error
	 * return proves the core did not start.
	 */
	s->may_run = 1;
	ret = s->ops->off(s->ctx);
	if (ret)
		goto fail;
	s->loaded = 0;
	ret = s->ops->wake(s->ctx);
	if (!ret)
		return 0;
fail:
	s->last_error = ret;
	smoke_recover(s);
	return ret;
}
