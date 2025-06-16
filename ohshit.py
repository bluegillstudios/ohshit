#!/usr/bin/env python3
import subprocess
import sys
import argparse
from colorama import init, Fore, Style
from datetime import datetime
import os
import json
import shutil

VERSION = "0.1.34"

# Global flags for color and verbosity
USE_COLOR = True
VERBOSE = False
QUIET = False

def init_colorama(color_mode):
    # color_mode: 'auto', 'always', 'never'
    # Initialize colorama accordingly
    if color_mode == 'never':
        # Disable color by overriding color codes with empty strings
        global Fore, Style
        class DummyColor:
            def __getattr__(self, name):
                return ''
        Fore = Style = DummyColor()
        # no init needed
    else:
        init(autoreset=True)

def cprint(text, color=Fore.RESET, end='\n', force=False):
    # Print respecting QUIET and USE_COLOR
    if QUIET and not force:
        return
    if USE_COLOR:
        print(color + text + Style.RESET_ALL, end=end)
    else:
        print(text, end=end)

OHSHIT_BACKUP_DIR = os.path.expanduser("~/.ohshit-backups")
OHSHIT_HISTORY_FILE = os.path.expanduser("~/.ohshit-history.json")

def run_git_command(cmd, dry_run=False, verbose=False):
    full_cmd = ['git'] + cmd
    if dry_run:
        cprint(Fore.YELLOW + '[dry-run] Would run: ' + ' '.join(full_cmd))
        return 0, ''
    if verbose:
        cprint(Fore.CYAN + '[run] git ' + ' '.join(cmd))
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, check=True)
        return result.returncode, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        cprint(Fore.RED + f"Git command failed: {' '.join(full_cmd)}")
        cprint(Fore.RED + e.stderr.strip())
        return e.returncode, e.stderr.strip()

def confirm(prompt, assume_yes=False):
    if assume_yes:
        cprint(Fore.CYAN + f"{prompt} [y/N] Auto-confirmed yes by --yes/--force.")
        return True
    ans = input(Fore.CYAN + prompt + " [y/N]: ").strip().lower()
    return ans == 'y'

def get_current_branch():
    code, branch = run_git_command(['rev-parse', '--abbrev-ref', 'HEAD'], verbose=VERBOSE)
    if code != 0:
        return None
    return branch

def last_commit_pushed(branch):
    code, local_hash = run_git_command(['rev-parse', 'HEAD'], verbose=VERBOSE)
    code2, remote_hash = run_git_command(['rev-parse', f'origin/{branch}'], verbose=VERBOSE)
    if code != 0 or code2 != 0:
        return False
    return local_hash == remote_hash

def is_git_repo():
    code, output = run_git_command(['rev-parse', '--is-inside-work-tree'], verbose=VERBOSE)
    return code == 0 and output == 'true'

def stash_exists():
    code, output = run_git_command(['stash', 'list'], verbose=VERBOSE)
    return code == 0 and output.strip() != ''

def backup_branch(branch, dry_run=False):
    if not os.path.exists(OHSHIT_BACKUP_DIR):
        os.makedirs(OHSHIT_BACKUP_DIR)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"ohshit-backup-{branch}-{timestamp}"
    cprint(Fore.BLUE + f"Backing up branch '{branch}' as '{backup_name}'...")
    code = run_git_command(['branch', backup_name], dry_run=dry_run, verbose=VERBOSE)[0]
    if code == 0:
        cprint(Fore.GREEN + f"Backup created: {backup_name}")
    else:
        cprint(Fore.RED + "Backup failed.")
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
        cprint(Fore.RED + "Warning: Failed to write to ohshit history.")

def undo_last_pushed_commit(dry_run, assume_yes, ignore_stash):
    branch = get_current_branch()
    if not branch:
        cprint(Fore.RED + "Error: Could not determine current branch.")
        return 1

    if stash_exists() and not ignore_stash:
        cprint(Fore.YELLOW + "Warning: You have stashed changes.")
        if not confirm("Continue anyway?", assume_yes):
            cprint("Aborted.")
            return 1

    if not last_commit_pushed(branch):
        cprint(Fore.YELLOW + f"Warning: The last commit on branch '{branch}' does NOT appear pushed to origin.")
        if not confirm("Continue with undo anyway?", assume_yes):
            cprint("Aborted.")
            return 1

    prompt = f"Are you sure you want to undo the last pushed commit on branch '{branch}'? This will reset HEAD~1 and force-push."
    if not confirm(prompt, assume_yes):
        cprint("Aborted.")
        return 1

    cprint(Fore.GREEN + "Resetting last commit locally...")
    code = run_git_command(['reset', '--hard', 'HEAD~1'], dry_run=dry_run, verbose=VERBOSE)[0]
    if code != 0:
        return code

    cprint(Fore.GREEN + "Force pushing branch to remote...")
    code = run_git_command(['push', '--force'], dry_run=dry_run, verbose=VERBOSE)[0]
    if code != 0:
        return code

    log_history('undo-pushed', {'branch': branch})
    cprint(Fore.GREEN + "Done. Crisis averted.")
    return 0

def undo_last_local_commit(dry_run, assume_yes, ignore_stash):
    if stash_exists() and not ignore_stash:
        cprint(Fore.YELLOW + "Warning: You have stashed changes.")
        if not confirm("Continue anyway?", assume_yes):
            cprint("Aborted.")
            return 1

    prompt = "Undo the last local commit, keeping changes staged?"
    if not confirm(prompt, assume_yes):
        cprint("Aborted.")
        return 1
    cprint(Fore.GREEN + "Resetting last commit softly (keeping changes)...")
    code = run_git_command(['reset', '--soft', 'HEAD~1'], dry_run=dry_run, verbose=VERBOSE)[0]
    if code == 0:
        log_history('undo-commit', {'commits': 1})
    return code

def force_push(dry_run, assume_yes):
    branch = get_current_branch()
    if not branch:
        cprint(Fore.RED + "Error: Could not determine current branch.")
        return 1
    prompt = f"Force push branch '{branch}' to remote?"
    if not confirm(prompt, assume_yes):
        cprint("Aborted.")
        return 1
    cprint(Fore.GREEN + f"Force pushing branch '{branch}'...")
    code = run_git_command(['push', '--force'], dry_run=dry_run, verbose=VERBOSE)[0]
    if code == 0:
        log_history('force-push', {'branch': branch})
    return code

def delete_branch(branch_name, dry_run, assume_yes):
    prompt = f"Are you sure you want to delete local branch '{branch_name}'?"
    if not confirm(prompt, assume_yes):
        cprint("Aborted.")
        return 1
    cprint(Fore.GREEN + f"Deleting branch '{branch_name}'...")
    code = run_git_command(['branch', '-D', branch_name], dry_run=dry_run, verbose=VERBOSE)[0]
    if code == 0:
        log_history('delete-branch', {'branch': branch_name})
    return code

def remove_remote(remote_name, dry_run, assume_yes):
    prompt = f"Are you sure you want to remove remote '{remote_name}'?"
    if not confirm(prompt, assume_yes):
        cprint("Aborted.")
        return 1
    cprint(Fore.GREEN + f"Removing remote '{remote_name}'...")
    code = run_git_command(['remote', 'remove', remote_name], dry_run=dry_run, verbose=VERBOSE)[0]
    if code == 0:
        log_history('remove-remote', {'remote': remote_name})
    return code

def status_summary():
    branch = get_current_branch()
    if not branch:
        cprint(Fore.RED + "Error: Could not determine current branch.")
        return 1

    code, last_commit = run_git_command(['log', '-1', '--pretty=%s'], verbose=VERBOSE)
    code2, remote_url = run_git_command(['remote', 'get-url', 'origin'], verbose=VERBOSE)

    cprint(Fore.CYAN + f"Branch: {branch}")
    cprint(Fore.CYAN + f"Last commit: {last_commit if code == 0 else 'N/A'}")
    cprint(Fore.CYAN + f"Remote origin: {remote_url if code2 == 0 else 'N/A'}")
    return 0

def shit_n_commits(n, dry_run=False, assume_yes=False, ignore_stash=False):
    if n <= 0:
        cprint(Fore.RED + "Error: Please specify a positive number of commits to go back, e.g. -3.")
        return 1

    if stash_exists() and not ignore_stash:
        cprint(Fore.YELLOW + "Warning: You have stashed changes.")
        if not confirm("Continue anyway?", assume_yes):
            cprint("Aborted.")
            return 1

    if not is_git_repo():
        cprint(Fore.RED + "Error: Not inside a Git repository. Exiting.")
        return 1

    branch = get_current_branch()
    if not branch:
        cprint(Fore.RED + "Error: Could not determine current branch.")
        return 1

    prompt = f"Are you sure you want to softly reset {n} commits on branch '{branch}'? Changes will be kept staged."
    if not confirm(prompt, assume_yes):
        cprint("Aborted.")
        return 1

    backup_branch(branch, dry_run)
    cprint(Fore.GREEN + f"Soft resetting HEAD~{n} (keeping changes staged)...")
    code = run_git_command(['reset', '--soft', f'HEAD~{n}'], dry_run=dry_run, verbose=VERBOSE)[0]
    if code != 0:
        return code

    log_history('shit', {'branch': branch, 'commits': n})
    cprint(Fore.GREEN + f"💩 Done. {n} commits backed out but changes are still staged.")
    return 0

def run_doctor():
    cprint(Fore.CYAN + "🩺 ohshit doctor report")

    if not is_git_repo():
        cprint(Fore.RED + "✘ Not inside a Git repository.")
        return 1

    branch = get_current_branch()
    if not branch:
        cprint(Fore.RED + "✘ Could not determine current branch.")
    else:
        cprint(Fore.GREEN + f"✔ On branch: {branch}")

    # Detached HEAD check
    code, head_status = run_git_command(['symbolic-ref', '--short', 'HEAD'], verbose=VERBOSE)
    if code != 0:
        cprint(Fore.YELLOW + "⚠ Detached HEAD state")
    else:
        cprint(Fore.GREEN + "✔ Not in detached HEAD")

    # Merge/Rebase checks
    git_dir = subprocess.run(['git', 'rev-parse', '--git-dir'], capture_output=True, text=True).stdout.strip()
    merge_in_progress = os.path.exists(os.path.join(git_dir, 'MERGE_HEAD'))
    rebase_in_progress = any(os.path.exists(os.path.join(git_dir, d)) for d in ['rebase-apply', 'rebase-merge'])
    cprint(Fore.YELLOW + "⚠ Merge in progress" if merge_in_progress else Fore.GREEN + "✔ No merge in progress")
    cprint(Fore.YELLOW + "⚠ Rebase in progress" if rebase_in_progress else Fore.GREEN + "✔ No rebase in progress")

    # Working tree status
    code, status = run_git_command(['status', '--porcelain'], verbose=VERBOSE)
    if status:
        cprint(Fore.YELLOW + "⚠ Working tree has uncommitted changes")
        # Check for untracked files (those starting with '??')
        untracked = [line for line in status.splitlines() if line.startswith('??')]
        if untracked:
            cprint(Fore.YELLOW + f"⚠ Untracked files present ({len(untracked)})")
    else:
        cprint(Fore.GREEN + "✔ Working tree is clean")

    # Stashes
    if stash_exists():
        cprint(Fore.YELLOW + "⚠ You have stashes")
    else:
        cprint(Fore.GREEN + "✔ No stashes")

    # Upstream check for current branch
    code_up, upstream = run_git_command(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}'], verbose=VERBOSE)
    if code_up != 0:
        cprint(Fore.YELLOW + "⚠ Current branch has NO upstream set")
    else:
        cprint(Fore.GREEN + f"✔ Upstream branch set: {upstream}")

    # Compare local vs remote and base commits
    local_hash = run_git_command(['rev-parse', branch], verbose=VERBOSE)[1]
    remote_hash = run_git_command(['rev-parse', f'origin/{branch}'], verbose=VERBOSE)[1]
    base_hash = run_git_command(['merge-base', branch, f'origin/{branch}'], verbose=VERBOSE)[1]

    if local_hash == remote_hash:
        cprint(Fore.GREEN + f"✔ Local is up-to-date with origin/{branch}")
    elif local_hash == base_hash:
        cprint(Fore.YELLOW + f"⚠ Local is behind origin/{branch}")
    elif remote_hash == base_hash:
        cprint(Fore.YELLOW + f"⚠ Local is ahead of origin/{branch}")
    else:
        cprint(Fore.RED + f"✘ Local and origin/{branch} have diverged")

    # Check for large files in last 5 commits (Optional, can be skipped if too slow)
    try:
        cprint(Fore.CYAN + "Checking for large files (>10MB) in last 5 commits...")
        cmd = ['rev-list', '--objects', '--all', '-n', '5']
        code, commits = run_git_command(cmd, verbose=VERBOSE)
        if code == 0:
            # Just an example, could be improved
            large_files = []
            # Use 'git verify-pack' requires packfiles, so let's skip for now to avoid complexity
            cprint(Fore.GREEN + "✔ Large file check skipped (complexity)")
    except Exception:
        cprint(Fore.YELLOW + "⚠ Could not check large files")

    # Check if .gitignore exists and is non-empty
    gitignore_path = os.path.join(os.getcwd(), '.gitignore')
    if not os.path.exists(gitignore_path):
        cprint(Fore.YELLOW + "⚠ .gitignore file is missing")
    else:
        if os.path.getsize(gitignore_path) == 0:
            cprint(Fore.YELLOW + "⚠ .gitignore file is empty")
        else:
            cprint(Fore.GREEN + "✔ .gitignore file exists and is not empty")

    # Local branches without upstream
    code, branches = run_git_command(['branch', '-vv'], verbose=VERBOSE)
    if code == 0:
        no_upstream = []
        for line in branches.splitlines():
            # Lines like:  "* branchname 1234567 [origin/branch: ahead 1] Commit message"
            # or: "  branchname 1234567 Commit message" (no upstream)
            parts = line.split()
            if len(parts) >= 3 and not ('[' in line and ']' in line):
                no_upstream.append(parts[1])
        if no_upstream:
            cprint(Fore.YELLOW + f"⚠ Local branches without upstream: {', '.join(no_upstream)}")
        else:
            cprint(Fore.GREEN + "✔ All local branches have upstreams")

    return 0

def show_history(limit=None):
    if not os.path.exists(OHSHIT_HISTORY_FILE):
        cprint(Fore.YELLOW + "No history found.")
        return 0

    try:
        with open(OHSHIT_HISTORY_FILE, 'r') as f:
            history = json.load(f)
    except Exception as e:
        cprint(Fore.RED + f"Failed to read history file: {e}")
        return 1

    if limit is not None:
        history = history[-limit:]

    if not history:
        cprint(Fore.YELLOW + "History is empty.")
        return 0

    action_colors = {
        'undo-pushed': Fore.RED,
        'undo-commit': Fore.RED,
        'force-push': Fore.MAGENTA,
        'delete-branch': Fore.YELLOW,
        'remove-remote': Fore.YELLOW,
        'shit': Fore.CYAN,
    }

    cprint(Fore.CYAN + f"Showing last {len(history)} history entries:")

    for entry in history:
        ts = entry.get('timestamp', 'N/A')
        action = entry.get('action', 'N/A')
        details = entry.get('details', {})
        color = action_colors.get(action, Fore.WHITE)
        detail_str = ', '.join(f"{k}={v}" for k,v in details.items()) if isinstance(details, dict) else str(details)
        cprint(f"{Fore.GREEN}{ts} {color}{action} {Fore.WHITE}{detail_str}")

    return 0

def main():
    global USE_COLOR, VERBOSE, QUIET

    parser = argparse.ArgumentParser(description="ohshit - undo Git mistakes quickly")
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    parser.add_argument('--dry-run', action='store_true', help='Show commands without executing')
    parser.add_argument('--yes', '-y', action='store_true', help='Assume yes for all prompts')
    parser.add_argument('--force', action='store_true', help='Alias for --yes')
    parser.add_argument('--ignore-stash', action='store_true', help='Ignore stashed changes warnings')
    parser.add_argument('--color', choices=['auto', 'always', 'never'], default='auto', help='Colorize output')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress output except errors')

    subparsers = parser.add_subparsers(dest='command', required=True)

    # undo last pushed commit
    subparsers.add_parser('undo-pushed', help='Undo last pushed commit')

    # undo last local commit
    subparsers.add_parser('undo', help='Undo last local commit')

    # force push current branch
    subparsers.add_parser('force-push', help='Force push current branch')

    # delete local branch
    delete_branch_parser = subparsers.add_parser('delete-branch', help='Delete local branch')
    delete_branch_parser.add_argument('branch_name', help='Branch to delete')

    # remove remote
    remove_remote_parser = subparsers.add_parser('remove-remote', help='Remove Git remote')
    remove_remote_parser.add_argument('remote_name', help='Remote to remove')

    # status
    subparsers.add_parser('status', help='Show Git repository status summary')

    # shit N commits
    shit_parser = subparsers.add_parser('shit', help='Undo last N commits softly (keep changes staged)')
    shit_parser.add_argument('n', type=int, help='Number of commits to undo')

    # doctor
    subparsers.add_parser('doctor', help='Run Git sanity checks')

    history_parser = subparsers.add_parser('history', help='Show ohshit command history')
    history_parser.add_argument('--limit', type=int, default=None, help='Limit number of history entries')

    args = parser.parse_args()

    # Set global flags
    VERBOSE = args.verbose
    QUIET = args.quiet
    USE_COLOR = (args.color == 'always') or (args.color == 'auto' and sys.stdout.isatty())

    init_colorama(args.color)

    dry_run = args.dry_run
    assume_yes = args.yes or args.force
    ignore_stash = args.ignore_stash

    if args.command == 'undo-pushed':
        return undo_last_pushed_commit(dry_run, assume_yes, ignore_stash)

    elif args.command == 'undo':
        return undo_last_local_commit(dry_run, assume_yes, ignore_stash)

    elif args.command == 'force-push':
        return force_push(dry_run, assume_yes)

    elif args.command == 'delete-branch':
        return delete_branch(args.branch_name, dry_run, assume_yes)

    elif args.command == 'remove-remote':
        return remove_remote(args.remote_name, dry_run, assume_yes)

    elif args.command == 'status':
        return status_summary()

    elif args.command == 'shit':
        return shit_n_commits(args.n, dry_run, assume_yes, ignore_stash)

    elif args.command == 'doctor':
        return run_doctor()

    elif args.command == 'history':
        return show_history(args.limit)

    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
