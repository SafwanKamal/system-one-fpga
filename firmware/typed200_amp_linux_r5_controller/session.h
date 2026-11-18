/* SPDX-License-Identifier: GPL-2.0-only */
/* Two TCMA leases, one mapping, one fixed smoke image. Caller serializes calls.
 * All callbacks return zero on success, negative errno on failure, except
 * lease(): 0 = no current/other owner, 1 = exclusively ours, negative = unknown
 * or another owner. No operation is retried automatically after ambiguous wake.
 */
#ifndef SYSONE_R5_SESSION_H
#define SYSONE_R5_SESSION_H
struct smoke_ops {
	int (*pin)(void *);
	void (*unpin)(void *);
	int (*reserve)(void *);
	void (*unreserve)(void *);
	int (*inspect)(void *);
	int (*request)(void *, unsigned int bank);
	int (*lease)(void *, unsigned int bank);
	int (*release)(void *, unsigned int bank);
	int (*stop)(void *);
	int (*off)(void *);
	int (*map)(void *);
	void (*unmap)(void *);
	int (*load)(void *);
	int (*wake)(void *);
};
struct smoke_session {
	const struct smoke_ops *ops;
	void *ctx;
	int pinned, reserved, lease_pending, mapped, may_run, loaded;
	int quarantined, last_error, recovery_error;
};
int smoke_recover(struct smoke_session *s);
int smoke_prepare(struct smoke_session *s);
int smoke_start(struct smoke_session *s);
#endif
