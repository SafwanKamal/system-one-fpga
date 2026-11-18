#!/bin/sh
# Run with sudo on the KR260. Does not rebuild FIT or reboot.
set -eu
test "$(id -u)" = 0 || { echo 'Run this script with sudo' >&2; exit 1; }
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test -d /etc/kernel/postinst.d
test -d /etc/initramfs/post-update.d
# Check the source DTB before installing hooks.
python3 "$script_dir/patch_kernel_dtb.py" --version "$(uname -r)"
install -d -m 755 /usr/local/lib/sysone
install -m 644 "$script_dir/patch_kernel_dtb.py" "$script_dir/prepare_reserved_fit.py" /usr/local/lib/sysone/
for hook_dir in /etc/kernel/postinst.d /etc/initramfs/post-update.d; do
    hook="$hook_dir/00-sysone-reserved-memory"
    if [ -e "$hook" ] && ! grep -q '^# System One KR260 reserved-memory hook$' "$hook"; then
        echo "Refusing to replace another hook: $hook" >&2
        exit 1
    fi
    cat > "$hook" <<'EOF'
#!/bin/sh
# System One KR260 reserved-memory hook
set -eu
exec /usr/bin/python3 /usr/local/lib/sysone/patch_kernel_dtb.py --version "${1:?kernel version required}"
EOF
    chmod 755 "$hook"
done
echo 'Installed hooks (listed in execution order):'
run-parts --test /etc/kernel/postinst.d
run-parts --test /etc/initramfs/post-update.d
echo 'Current kernel DTB patched. FIT not rebuilt; reboot not requested.'
