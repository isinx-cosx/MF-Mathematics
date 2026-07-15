# -*- coding: utf-8 -*-
"""MF_User — 用户管理系统。

提供用户注册、登录、会话管理。
当前使用内存存储，后续可切换为本地文件或云端数据库。

用法:
    from MF_User import UserManager

    mgr = UserManager()
    user, err = mgr.register("alice", "password123")
    user, err = mgr.login("alice", "password123")
    if mgr.is_logged_in:
        print(f"当前用户: {mgr.current_user.username}")
    mgr.logout()
"""

from __future__ import annotations

from MF_User.models import User
from MF_User.manager import UserManager

__all__ = ["User", "UserManager"]


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """运行所有子模块 self_test。"""
    total_passed, total_failed = 0, 0
    all_errors: list[str] = []

    modules = [
        ("manager", "MF_User.manager"),
        ("login_dialog", "MF_User.login_dialog"),
        ("register_dialog", "MF_User.register_dialog"),
    ]

    print("=" * 60)
    print("MF_User 包级 self_test")
    print("=" * 60)

    for name, module_path in modules:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            if hasattr(mod, 'self_test'):
                p, f, e = mod.self_test()
                total_passed += p
                total_failed += f
                all_errors.extend(e)
                print(f"  [{name}] {p} passed, {f} failed")
            else:
                print(f"  [{name}] 无 self_test, 跳过")
        except Exception as e:
            total_failed += 1
            all_errors.append(f"{name}: {e}")
            print(f"  [{name}] ERROR: {e}")

    print(f"\n总计: {total_passed} passed, {total_failed} failed")
    if all_errors:
        for e in all_errors:
            print(f"  [ERROR] {e}")
    print("=" * 60)
    return total_passed, total_failed, all_errors


if __name__ == "__main__":
    self_test()
