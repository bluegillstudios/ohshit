#!/usr/bin/env python3
import subprocess
import sys
import argparse
from colorama import init, Fore, Style
from datetime import datetime
import os
import json

VERSION = "0.1.2"

init(autoreset=True)

OHSHIT_BACKUP_DIR = os.path.expanduser("~/.ohshit-backups")
OHSHIT_HISTORY_FILE = os.path.expanduser("~/.ohshit-history.json")


def run_git_command(cmd, dry_run=False):
    full_cmd = ['git'] + cmd
    if dry_run:
        print(Fore.YELLOW + '[dry-run] Would run: ' + ' '.join(full_cmd))
        return 0, ''
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, check=True)
        return result.returncode, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(Fore.RED + f"Git command failed: {' '.join(full_cmd)}")
        print(Fore.RED + e.stderr.strip())
        return e.returncode, e.stderr.strip()


def confirm(prompt, assume_yes=False):
    if assume_yes:
        print(Fore.CYAN + f"{prompt} [y/N] Auto-confirmed yes by --yes/--force.")
        return True
    ans = input(Fore.CYAN + prompt + " [y/N]: ").strip().lower()
    return ans == 'y'


def get_current_branch():
    code, branch = run_git_command(['rev-parse', '--abbrev-ref', 'HEAD'])
    if code != 0:
        return None
    return branch


def last_commit_pushed(branch):
    code, local_hash = run_git_command(['rev-parse', 'HEAD'])
    code2, remote_hash = run_git_command(['rev-parse', f'origin/{branch}'])
    if code != 0 or code2 != 0:
        return False
    return local_hash == remote_hash


def is_git_repo():
    code, output = run_git_command(['rev-parse', '--is-inside-work-tree'])
    return code == 0 and output == 'true'


def stash_exists():
    code, output = run_git_command(['stash', 'list'])
    return code == 0 and output.strip() != ''


def backup_branch(branch, dry_run=False):
    if not os.path.exists(OHSHIT_BACKUP_DIR):
        os.makedirs(OHSHIT_BACKUP_DIR)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"ohshit-backup-{branch}-{timestamp}"
    print(Fore.BLUE + f"Backing up branch '{branch}' as '{backup_name}'...")
    code = run_git_command(['branch', backup_name], dry_run=dry_run)[0]
    if code == 0:
        print(Fore.GREEN + f"Backup created: {backup_name}")
    else:
        print(Fore.RED + "Backup failed.")
    return backup_name if code == 0 else None


def log_history(action, details):
    history = []
    if os.path.exists(OHSHIT_HISTORY_FILE):
        try:
            with open(OHSHIT_HISTORY_FILE, 'r') as f:
                history = json.load(f)
        except Exception:
            pass
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details
    }
    history.append(entry)
    try:
        with open(OHSHIT_HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception:
        print(Fore.RED + "Warning: Failed to write to ohshit history.")


def undo_last_pushed_commit(dry_run, assume_yes, ignore_stash):
    branch = get_current_branch()
    if not branch:
        print(Fore.RED + "Error: Could not determine current branch.")
        return 1

    if stash_exists() and not ignore_stash:
        print(Fore.YELLOW + "Warning: You have stashed changes.")
        if not confirm("Continue anyway?", assume_yes):
            print("Aborted.")
            return 1

    if not last_commit_pushed(branch):
        print(Fore.YELLOW + f"Warning: The last commit on branch '{branch}' does NOT appear pushed to origin.")
        if not confirm("Continue with undo anyway?", assume_yes):
            print("Aborted.")
            return 1

    prompt = f"Are you sure you want to undo the last pushed commit on branch '{branch}'? This will reset HEAD~1 and force-push."
    if not confirm(prompt, assume_yes):
        print("Aborted.")
        return 1

    print(Fore.GREEN + "Resetting last commit locally...")
    code = run_git_command(['reset', '--hard', 'HEAD~1'], dry_run=dry_run)[0]
    if code != 0:
        return code

    print(Fore.GREEN + "Force pushing branch to remote...")
    code = run_git_command(['push', '--force'], dry_run=dry_run)[0]
    if code != 0:
        return code

    log_history('undo-pushed', {'branch': branch})
    print(Fore.GREEN + "Done. Crisis averted.")
    return 0


def undo_last_local_commit(dry_run, assume_yes, ignore_stash):
    if stash_exists() and not ignore_stash:
        print(Fore.YELLOW + "Warning: You have stashed changes.")
        if not confirm("Continue anyway?", assume_yes):
            print("Aborted.")
            return 1

    prompt = "Undo the last local commit, keeping changes staged?"
    if not confirm(prompt, assume_yes):
        print("Aborted.")
        return 1
    print(Fore.GREEN + "Resetting last commit softly (keeping changes)...")
    code = run_git_command(['reset', '--soft', 'HEAD~1'], dry_run=dry_run)[0]
    if code == 0:
        log_history('undo-commit', {'commits': 1})
    return code


def force_push(dry_run, assume_yes):
    branch = get_current_branch()
    if not branch:
        print(Fore.RED + "Error: Could not determine current branch.")
        return 1
    prompt = f"Force push branch '{branch}' to remote?"
    if not confirm(prompt, assume_yes):
        print("Aborted.")
        return 1
    print(Fore.GREEN + f"Force pushing branch '{branch}'...")
    code = run_git_command(['push', '--force'], dry_run=dry_run)[0]
    if code == 0:
        log_history('force-push', {'branch': branch})
    return code


def delete_branch(branch_name, dry_run, assume_yes):
    prompt = f"Are you sure you want to delete local branch '{branch_name}'?"
    if not confirm(prompt, assume_yes):
        print("Aborted.")
        return 1
    print(Fore.GREEN + f"Deleting branch '{branch_name}'...")
    code = run_git_command(['branch', '-D', branch_name], dry_run=dry_run)[0]
    if code == 0:
        log_history('delete-branch', {'branch': branch_name})
    return code


def remove_remote(remote_name, dry_run, assume_yes):
    prompt = f"Are you sure you want to remove remote '{remote_name}'?"
    if not confirm(prompt, assume_yes):
        print("Aborted.")
        return 1
    print(Fore.GREEN + f"Removing remote '{remote_name}'...")
    code = run_git_command(['remote', 'remove', remote_name], dry_run=dry_run)[0]
    if code == 0:
        log_history('remove-remote', {'remote': remote_name})
    return code


def status_summary():
    branch = get_current_branch()
    if not branch:
        print(Fore.RED + "Error: Could not determine current branch.")
        return 1

    code, last_commit = run_git_command(['log', '-1', '--pretty=%s'])
    code2, remote_url = run_git_command(['remote', 'get-url', 'origin'])

    print(Fore.CYAN + f"Branch: {branch}")
    print(Fore.CYAN + f"Last commit: {last_commit if code == 0 else 'N/A'}")
    print(Fore.CYAN + f"Remote origin: {remote_url if code2 == 0 else 'N/A'}")
    return 0


def shit_n_commits(n, dry_run=False, assume_yes=False, ignore_stash=False):
    if n <= 0:
        print(Fore.RED + "Error: Please specify a positive number of commits to go back, e.g. -3.")
        return 1

    if stash_exists() and not ignore_stash:
        print(Fore.YELLOW + "Warning: You have stashed changes.")
        if not confirm("Continue anyway?", assume_yes):
            print("Aborted.")
            return 1

    if not is_git_repo():
        print(Fore.RED + "Error: Not inside a Git repository. Exiting.")
        return 1

    branch = get_current_branch()
    if not branch:
        print(Fore.RED + "Error: Could not determine current branch.")
        return 1

    prompt = f"Are you sure you want to softly reset {n} commits on branch '{branch}'? Changes will be kept staged."
    if not confirm(prompt, assume_yes):
        print("Aborted.")
        return 1

    backup_branch(branch, dry_run)
    print(Fore.GREEN + f"Soft resetting HEAD~{n} (keeping changes staged)...")
    code = run_git_command(['reset', '--soft', f'HEAD~{n}'], dry_run=dry_run)[0]
    if code != 0:
        return code

    log_history('shit', {'branch': branch, 'commits': n})
    print(Fore.GREEN + f"💩 Done. {n} commits backed out but changes are still staged.")
    return 0

def run_doctor():
    print(Fore.CYAN + "🩺 ohshit doctor report")
    if not is_git_repo():
        print(Fore.RED + "✘ Not inside a Git repository.")
        return 1

    branch = get_current_branch()
    if not branch:
        print(Fore.RED + "✘ Could not determine current branch.")
    else:
        print(Fore.GREEN + f"✔ On branch: {branch}")

    code, head_status = run_git_command(['symbolic-ref', '--short', 'HEAD'])
    if code != 0:
        print(Fore.YELLOW + "⚠ Detached HEAD state")
    else:
        print(Fore.GREEN + "✔ Not in detached HEAD")

    git_dir = subprocess.run(['git', 'rev-parse', '--git-dir'], capture_output=True, text=True).stdout.strip()
    merge_in_progress = os.path.exists(os.path.join(git_dir, 'MERGE_HEAD'))
    rebase_in_progress = any(os.path.exists(os.path.join(git_dir, d)) for d in ['rebase-apply', 'rebase-merge'])

    print(Fore.YELLOW + "⚠ Merge in progress" if merge_in_progress else Fore.GREEN + "✔ No merge in progress")
    print(Fore.YELLOW + "⚠ Rebase in progress" if rebase_in_progress else Fore.GREEN + "✔ No rebase in progress")

    code, status = run_git_command(['status', '--porcelain'])
    print(Fore.YELLOW + "⚠ Working tree has uncommitted changes" if status else Fore.GREEN + "✔ Working tree is clean")

    if stash_exists():
        print(Fore.YELLOW + "⚠ You have stashes")
    else:
        print(Fore.GREEN + "✔ No stashes")

    branch = get_current_branch()
    if not branch:
        print(Fore.RED + "✘ Could not determine current branch for upstream checks.")
        return 1

    local_hash = run_git_command(['rev-parse', branch])[1]
    remote_hash = run_git_command(['rev-parse', f'origin/{branch}'])[1]
    base_hash = run_git_command(['merge-base', branch, f'origin/{branch}'])[1]
    if local_hash == remote_hash:
        print(Fore.GREEN + f"✔ Local is up-to-date with origin/{branch}")
    elif local_hash == base_hash:
        print(Fore.YELLOW + f"⚠ Local is behind origin/{branch}")
    elif remote_hash == base_hash:
        print(Fore.YELLOW + f"⚠ Local is ahead of origin/{branch}")
    else:
        print(Fore.RED + f"✘ Local and origin/{branch} have diverged")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="ohshit - quick git undo tool for your fuck-ups."
    )
    parser.add_argument('action', nargs='?', default='undo-pushed',
                        choices=['undo-pushed', 'commit', 'push', 'branch', 'remote', 'status', 'shit', 'doctor', 'help'],
                        help="Action to perform (default: undo-pushed)")
    parser.add_argument('target', nargs='?', help="Branch or remote name for delete/remove actions, or argument for 'shit' (e.g. -3).")
    parser.add_argument('--dry-run', action='store_true', help="Show commands without running.")
    parser.add_argument('-y', '--yes', action='store_true', help="Skip confirmation prompts.")
    parser.add_argument('-f', '--force', action='store_true', help="Skip confirmation prompts (alias for --yes).")
    parser.add_argument('--ignore-stash-warning', action='store_true', help="Suppress warnings about existing stashes.")
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')

    args = parser.parse_args()
    assume_yes = args.yes or args.force

    if args.action == 'help':
        parser.print_help()
        sys.exit(0)

    if args.action == 'shit':
        if not args.target or not args.target.startswith('-'):
            print(Fore.RED + "Error: Please specify number of commits to go back, e.g. 'ohshit shit -3'")
            sys.exit(1)
        try:
            n = int(args.target.lstrip('-'))
        except ValueError:
            print(Fore.RED + "Error: Invalid number format.")
            sys.exit(1)
        sys.exit(shit_n_commits(n, args.dry_run, assume_yes, args.ignore_stash_warning))

    if not is_git_repo():
        print(Fore.RED + "Error: Not inside a Git repository. Exiting.")
        sys.exit(1)

    if args.action == 'undo-pushed':
        sys.exit(undo_last_pushed_commit(args.dry_run, assume_yes, args.ignore_stash_warning))
    elif args.action == 'commit':
        sys.exit(undo_last_local_commit(args.dry_run, assume_yes, args.ignore_stash_warning))
    elif args.action == 'push':
        sys.exit(force_push(args.dry_run, assume_yes))
    elif args.action == 'branch':
        if not args.target:
            print(Fore.RED + "Error: Branch name required for 'branch' action.")
            sys.exit(1)
        sys.exit(delete_branch(args.target, args.dry_run, assume_yes))
    elif args.action == 'remote':
        if not args.target:
            print(Fore.RED + "Error: Remote name required for 'remote' action.")
            sys.exit(1)
        sys.exit(remove_remote(args.target, args.dry_run, assume_yes))
    elif args.action == 'status':
        sys.exit(status_summary())
    elif args.action == 'doctor':
        sys.exit(run_doctor())
    else:
        print(Fore.RED + f"Unknown action '{args.action}'. Use --help for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
