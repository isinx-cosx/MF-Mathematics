# -*- coding: utf-8 -*-
"""MF_User — 用户认证系统。

提供在线登录、注册、邮箱验证及会话状态管理。

用法:
    from MF_User import AuthService, APIClient, LoginRegisterDialog

    # 打开登录对话框
    dlg = LoginRegisterDialog(parent)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        auth = AuthService()
        print(f"已登录: {auth.username}, 余额: {auth.balance}")

    # 后台获取用户信息
    from MF_User.auth_worker import AuthWorker
    worker = AuthWorker(parent, lambda: APIClient().get_me(auth.token))
    worker.succeeded.connect(lambda d: auth.update_profile(d))
    worker.start()
"""

from __future__ import annotations

from MF_User.auth_service import AuthService
from MF_User.api_client import APIClient
from MF_User.auth_worker import AuthWorker
from MF_User.login_dialog import LoginRegisterDialog, LoginDialog

__all__ = [
    "AuthService",
    "APIClient",
    "AuthWorker",
    "LoginRegisterDialog",
    "LoginDialog",
]


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """运行所有子模块 self_test。"""
    total_passed, total_failed = 0, 0
    all_errors: list[str] = []

    modules = [
        ("auth_service", "MF_User.auth_service"),
        ("auth_worker", "MF_User.auth_worker"),
        ("api_client", "MF_User.api_client"),
        ("login_dialog", "MF_User.login_dialog"),
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
