/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "session.h"

struct mock {
	uint64_t failures;
	int calls, effects, pinned, reserved, owner, mapped, active, verified;
	int wakes, requests, releases, stop_stuck, conflict;
};
static int tick(struct mock *m)
{
	m->calls++;
	return m->calls <= 63 && (m->failures & (1ULL << m->calls)) != 0;
}
static int pin(void *v)
{
	struct mock *m = v;
	if (tick(m)) return -EAGAIN;
	assert(!m->pinned); m->pinned = 1; return 0;
}
static void unpin(void *v)
{
	struct mock *m = v;
	assert(m->pinned && !m->reserved && !m->owner && !m->mapped && !m->active);
	m->pinned = 0;
}
static int reserve(void *v)
{
	struct mock *m = v;
	assert(m->pinned && !m->reserved);
	if (tick(m)) return -EBUSY;
	m->reserved = 1; return 0;
}
static void unreserve(void *v)
{
	struct mock *m = v;
	assert(m->reserved && !m->mapped && !m->owner && !m->active);
	m->reserved = 0;
}
static int inspect(void *v)
{
	struct mock *m = v;
	assert(!m->owner && !m->mapped && !m->active);
	return tick(m) || m->conflict ? -EACCES : 0;
}
static int request(void *v, unsigned int bank)
{
	struct mock *m = v;
	int fail = tick(m);
	assert(bank < 2 && !(m->owner & (1 << bank)) && m->reserved && m->pinned);
	m->requests++;
	if (!fail || m->effects) m->owner |= 1 << bank;
	m->verified = 0;
	return fail ? -EIO : 0;
}
static int lease(void *v, unsigned int bank)
{
	struct mock *m = v;
	assert(m->pinned && m->reserved);
	return tick(m) ? -ETIMEDOUT : !!(m->owner & (1 << bank));
}
static int release(void *v, unsigned int bank)
{
	struct mock *m = v;
	int fail = tick(m);
	assert((m->owner & (1 << bank)) && !m->active && !m->mapped && m->verified);
	m->releases++;
	if (!fail || m->effects) m->owner &= ~(1 << bank);
	return fail ? -EIO : 0;
}
static int stop(void *v)
{
	struct mock *m = v;
	int fail = tick(m) || m->stop_stuck;
	assert(m->pinned && m->reserved);
	if (!fail || (m->effects && !m->stop_stuck)) m->active = 0;
	m->verified = 0;
	return fail ? -EIO : 0;
}
static int off(void *v)
{
	struct mock *m = v;
	if (tick(m)) return -ETIMEDOUT;
	if (m->active) return -EBUSY;
	m->verified = 1; return 0;
}
static int map(void *v)
{
	struct mock *m = v;
	assert(!m->mapped && m->owner == 3 && !m->active && m->verified);
	if (tick(m)) return -ENOMEM;
	m->mapped = 1; return 0;
}
static void unmap(void *v)
{
	struct mock *m = v;
	assert(m->mapped && !m->active && m->verified);
	m->mapped = 0;
}
static int load(void *v)
{
	struct mock *m = v;
	assert(m->mapped && m->owner && m->verified && !m->active);
	return tick(m) ? -EIO : 0;
}
static int wake(void *v)
{
	struct mock *m = v;
	int fail = tick(m);
	assert(m->owner && m->mapped && m->verified);
	assert(m->wakes == 0); m->wakes++;
	if (!fail || m->effects) m->active = 1;
	m->verified = 0;
	return fail ? -EIO : 0;
}
static const struct smoke_ops ops = {
	pin, unpin, reserve, unreserve, inspect, request, lease, release,
	stop, off, map, unmap, load, wake
};
static int cases;
static int run(uint64_t failures, int effects)
{
	struct mock m = {.failures=failures, .effects=effects};
	struct smoke_session s = {.ops=&ops, .ctx=&m};
	if (!smoke_prepare(&s)) smoke_start(&s);
	int before = m.calls;
	for (int i=0; i<70 && s.pinned; i++) {
		if (s.quarantined) {
			assert(smoke_prepare(&s) == -EBUSY);
			assert(smoke_start(&s) == -EINVAL);
		}
		smoke_recover(&s);
	}
	assert(!s.pinned && !s.reserved && !s.lease_pending && !s.mapped && !s.may_run);
	assert(!s.quarantined && !m.owner && !m.mapped && !m.active);
	assert(!m.pinned && !m.reserved && m.wakes <= 1);
	assert(smoke_recover(&s) == 0);
	cases++;
	return before;
}
int main(void)
{
	int length = run(0, 0) + 8;
	for (int e=0; e<2; e++) {
		for (int a=1; a<=length; a++) {
			run(1ULL << a, e);
			for (int b=a+1; b<=length; b++) run((1ULL<<a)|(1ULL<<b), e);
		}
	}
	uint64_t rng = 0xa131b57;
	for (int i=0; i<10000; i++) {
		rng ^= rng<<13; rng ^= rng>>7; rng ^= rng<<17;
		run(rng & 0x7ffffffffffffffeULL, i%2);
	}
	/* Persistent failed stop must retain live memory, lease and module pin. */
	struct mock m = {0};struct smoke_session s={.ops=&ops,.ctx=&m};
	assert(smoke_prepare(&s)==0 && smoke_start(&s)==0);
	m.stop_stuck=1;
	for(int i=0;i<5;i++) {
		assert(smoke_recover(&s)<0);
		assert(s.quarantined && s.pinned && s.mapped && s.lease_pending && s.may_run);
		assert(m.owner && m.mapped && m.pinned && m.active && m.releases==0);
		assert(smoke_prepare(&s)==-EBUSY && smoke_start(&s)==-EINVAL);
	}
	m.stop_stuck=0;assert(smoke_recover(&s)==0);cases++;
	/* Ownership conflict fails before request or stop can touch either core. */
	memset(&m,0,sizeof m);memset(&s,0,sizeof s);s.ops=&ops;s.ctx=&m;m.conflict=1;
	assert(smoke_prepare(&s)==-EACCES && !s.pinned && m.requests==0);cases++;
	printf("PASS %d session failure/recovery trajectories; no cleanup before confirmed stop, no double release or automatic re-wake\n",cases);
	return 0;
}
