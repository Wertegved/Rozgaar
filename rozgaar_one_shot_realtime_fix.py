from __future__ import annotations

import argparse
import shutil
from pathlib import Path


FILES = {
    "admin_realtime": Path("admin-web/js/realtime.js"),
    "consumer_realtime": Path("consumer-web/js/realtime.js"),
    "worker_realtime": Path("worker-web/js/realtime.js"),
    "consumer_app": Path("consumer-web/js/app.js"),
    "worker_app": Path("worker-web/js/app.js"),
    "broadcast_service": Path("backend/app/realtime/service.py"),
    "config": Path("backend/app/core/config.py"),
}

BACKUP_SUFFIX = ".before-one-shot-fix.bak"


def backup(path: Path) -> None:
    backup_path = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    if not backup_path.exists():
        shutil.copy2(path, backup_path)


def replace_if_present(path: Path, old: str, new: str, description: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        return False
    if text.count(old) != 1:
        raise RuntimeError(f"{description}: expected exactly one match in {path}, found {text.count(old)}")
    backup(path)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def ensure_realtime_helper(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    changed: list[str] = []

    if "let connectPromise;" not in text:
        old = "  let supabaseModule;\n"
        new = "  let supabaseModule;\n  let connectPromise;\n  let sessionKey = null;\n"
        if replace_if_present(path, old, new, "add Realtime lifecycle state"):
            changed.append("added idempotent lifecycle state")
        text = path.read_text(encoding="utf-8")

    old_stop = "    clearTimeout(refreshTimer);\n    await resetClient();\n  };"
    new_stop = "    clearTimeout(refreshTimer);\n    sessionKey = null;\n    connectPromise = null;\n    await resetClient();\n  };"
    if "sessionKey = null;\n    connectPromise = null;\n    await resetClient();" not in text:
        if replace_if_present(path, old_stop, new_stop, "clear Realtime session state on stop"):
            changed.append("cleared lifecycle state on stop")
        text = path.read_text(encoding="utf-8")

    old_sub = ".subscribe((status) => {\n          options.onStatus?.(status);"
    new_sub = ".subscribe((status, error) => {\n          options.onStatus?.(status, error);"
    if old_sub in text and replace_if_present(path, old_sub, new_sub, "forward Realtime subscribe errors"):
        changed.append("forwarded subscription errors")
        text = path.read_text(encoding="utf-8")

    old_catch = "      options.onStatus?.('ERROR');"
    new_catch = "      options.onStatus?.('ERROR', error);"
    if old_catch in text and replace_if_present(path, old_catch, new_catch, "forward Realtime connection errors"):
        changed.append("forwarded connection errors")
        text = path.read_text(encoding="utf-8")

    if "nextSessionKey" not in text:
        old_start = "    start(next) { stopped = false; options = next; return connect(); },\n    stop() { stopped = true; options = null; return stop(); },"
        new_start = """    start(next) {
      const nextSessionKey = next?.user?.id && next?.token ? `${next.user.id}|${next.token}` : null;
      options = next;
      if (stopped || sessionKey !== nextSessionKey) {
        stopped = false;
        sessionKey = nextSessionKey;
        connectPromise = connect();
        connectPromise.finally(() => {
          if (sessionKey === nextSessionKey) connectPromise = null;
        });
        return connectPromise;
      }
      return connectPromise || Promise.resolve();
    },
    stop() { stopped = true; options = null; sessionKey = null; return stop(); },"""
        if replace_if_present(path, old_start, new_start, "make Realtime start idempotent"):
            changed.append("made start idempotent")
            text = path.read_text(encoding="utf-8")

    # Keep the stale-token defense even if the baseline helper is older.
    old_connect = "      await resetClient();\n\n    try {"
    # No replacement needed; verify the required line is present.
    if old_connect not in text:
        raise RuntimeError(f"{path}: connect() does not reset the authenticated client before fetching a fresh token")

    if "accessToken: async () => accessToken" not in text:
        raise RuntimeError(f"{path}: expected Supabase accessToken configuration is missing")

    if "config: { private: true }" not in text:
        raise RuntimeError(f"{path}: private Realtime channel configuration is missing")

    return changed


def patch_app_starts(root: Path) -> list[str]:
    changed: list[str] = []

    consumer = root / FILES["consumer_app"]
    text = consumer.read_text(encoding="utf-8")
    old = "if (path === '/auth/me' && body?.id && state.token) { state.user = body; startConsumerRealtime(); }"
    if old in text:
        if replace_if_present(
            consumer,
            old,
            "if (path === '/auth/me' && body?.id && state.token) state.user = body;",
            "remove Consumer Realtime start from generic API helper",
        ):
            changed.append("Consumer: removed duplicate Realtime start from api()")
            text = consumer.read_text(encoding="utf-8")
    elif "startConsumerRealtime();" in text and "body?.id && state.token" in text:
        raise RuntimeError(f"{consumer}: Consumer Realtime may still be started from the generic API helper; inspect manually")

    marker = "updateAuthState(); renderWorkspace(); } catch (error) {"
    addition = "updateAuthState(); renderWorkspace(); startConsumerRealtime(); } catch (error) {"
    text = consumer.read_text(encoding="utf-8")
    if "updateAuthState(); renderWorkspace(); startConsumerRealtime();" not in text:
        if replace_if_present(consumer, marker, addition, "start Consumer Realtime after workspace load"):
            changed.append("Consumer: start Realtime once after workspace load")

    worker = root / FILES["worker_app"]
    text = worker.read_text(encoding="utf-8")
    old = "if (path === '/auth/me' && body?.id && state.token) { state.user = body; startWorkerRealtime(); }"
    if old in text:
        if replace_if_present(
            worker,
            old,
            "if (path === '/auth/me' && body?.id && state.token) state.user = body;",
            "remove Worker Realtime start from generic API helper",
        ):
            changed.append("Worker: removed duplicate Realtime start from api()")
            text = worker.read_text(encoding="utf-8")
    elif "startWorkerRealtime();" in text and "body?.id && state.token" in text:
        raise RuntimeError(f"{worker}: Worker Realtime may still be started from the generic API helper; inspect manually")

    marker = "state.reviews = reviews?.items || []; state.complaints = complaints?.items || []; updateUserArea(); updateNavigation(); renderView(); } catch (error) {"
    addition = "state.reviews = reviews?.items || []; state.complaints = complaints?.items || []; updateUserArea(); updateNavigation(); renderView(); startWorkerRealtime(); } catch (error) {"
    text = worker.read_text(encoding="utf-8")
    if "updateUserArea(); updateNavigation(); renderView(); startWorkerRealtime();" not in text:
        if replace_if_present(worker, marker, addition, "start Worker Realtime after core load"):
            changed.append("Worker: start Realtime once after core load")

    return changed


def patch_broadcast(root: Path) -> list[str]:
    path = root / FILES["broadcast_service"]
    text = path.read_text(encoding="utf-8")
    changed: list[str] = []
    old = '            "Authorization": f"Bearer {settings.supabase_service_role_key}",\n            "Content-Type": "application/json",'
    new = '            "apikey": settings.supabase_service_role_key,\n            "Content-Type": "application/json",'
    if old in text:
        if replace_if_present(path, old, new, "use Supabase Realtime REST API key header"):
            changed.append("Broadcast REST transport: use apikey header")
    elif '"apikey": settings.supabase_service_role_key' not in text:
        raise RuntimeError(f"{path}: Realtime REST transport header is neither the known old form nor the expected apikey form")
    return changed


def verify_config(root: Path) -> list[str]:
    path = root / FILES["config"]
    text = path.read_text(encoding="utf-8")
    required = [
        'validation_alias="SUPABASE_URL"',
        'validation_alias="SUPABASE_ANON_KEY"',
        'validation_alias="SUPABASE_SERVICE_ROLE_KEY"',
        'validation_alias="SUPABASE_JWT_SECRET"',
    ]
    missing = [needle for needle in required if needle not in text]
    if missing:
        raise RuntimeError(
            f"{path}: required Supabase environment bindings are missing: {', '.join(missing)}"
        )
    return ["config.py: Supabase environment aliases verified"]


def apply(root: Path) -> None:
    root = root.resolve()
    if not (root / "backend").is_dir() or not (root / "admin-web").is_dir() or not (root / "consumer-web").is_dir() or not (root / "worker-web").is_dir():
        raise RuntimeError(f"{root} does not look like the Rozgaar repository root.")

    report: list[str] = []

    for name in ("admin_realtime", "consumer_realtime", "worker_realtime"):
        path = root / FILES[name]
        changed = ensure_realtime_helper(path)
        if changed:
            report.append(f"{path.relative_to(root)}: " + "; ".join(changed))
        else:
            report.append(f"{path.relative_to(root)}: no changes needed")

    report.extend(patch_app_starts(root))
    report.extend(patch_broadcast(root))
    report.extend(verify_config(root))

    print("\nOne-shot Rozgaar Realtime fix completed.\n")
    for item in report:
        print(f"- {item}")
    print("\nBackups use suffix:", BACKUP_SUFFIX)
    print("Next: rebuild/recreate the backend and run the narrow Realtime validation.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply the targeted final Rozgaar Realtime fixes.")
    parser.add_argument("root", nargs="?", default=".", help="Rozgaar repository root (default: current directory)")
    args = parser.parse_args()
    apply(Path(args.root))
