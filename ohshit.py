#!/usr/bin/env python3
import subprocess
import sys
import argparse
from colorama import init, Fore, Style

VERSION = "0.1.0"

init(autoreset=True)


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


def undo_last_pushed_commit(dry_run, assume_yes):
    branch = get_current_branch()
    if not branch:
        print(Fore.RED + "Error: Could not determine current branch.")
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

    print(Fore.GREEN + "Done. Crisis averted.")
    return 0


def undo_last_local_commit(dry_run, assume_yes):
    prompt = "Undo the last local commit, keeping changes staged?"
    if not confirm(prompt, assume_yes):
        print("Aborted.")
        return 1
    print(Fore.GREEN + "Resetting last commit softly (keeping changes)...")
    return run_git_command(['reset', '--soft', 'HEAD~1'], dry_run=dry_run)[0]


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
    return run_git_command(['push', '--force'], dry_run=dry_run)[0]


def delete_branch(branch_name, dry_run, assume_yes):
    prompt = f"Are you sure you want to delete local branch '{branch_name}'?"
    if not confirm(prompt, assume_yes):
        print("Aborted.")
        return 1
    print(Fore.GREEN + f"Deleting branch '{branch_name}'...")
    return run_git_command(['branch', '-D', branch_name], dry_run=dry_run)[0]


def remove_remote(remote_name, dry_run, assume_yes):
    prompt = f"Are you sure you want to remove remote '{remote_name}'?"
    if not confirm(prompt, assume_yes):
        print("Aborted.")
        return 1
    print(Fore.GREEN + f"Removing remote '{remote_name}'...")
    return run_git_command(['remote', 'remove', remote_name], dry_run=dry_run)[0]


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


def main():
    parser = argparse.ArgumentParser(
        description="ohshit - quick git undo tool for your fuck-ups."
    )
    parser.add_argument('action', nargs='?', default='undo-pushed',
                        choices=['undo-pushed', 'commit', 'push', 'branch', 'remote', 'status', 'help'],
                        help="Action to perform (default: undo-pushed)")
    parser.add_argument('target', nargs='?', help="Branch or remote name for delete/remove actions.")
    parser.add_argument('--dry-run', action='store_true', help="Show commands without running.")
    parser.add_argument('-y', '--yes', action='store_true', help="Skip confirmation prompts.")
    parser.add_argument('-f', '--force', action='store_true', help="Skip confirmation prompts (alias for --yes).")
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')

    args = parser.parse_args()
    assume_yes = args.yes or args.force
    if not is_git_repo():
	print(Fore.RED + "Error: Not inside a Git repository. Exiting.")
	sys.exit(1)

    if args.action == 'help':
        parser.print_help()
        sys.exit(0)

    if args.action == 'undo-pushed':
        sys.exit(undo_last_pushed_commit(args.dry_run, assume_yes))
    elif args.action == 'commit':
        sys.exit(undo_last_local_commit(args.dry_run, assume_yes))
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
    else:
        print(Fore.RED + f"Unknown action '{args.action}'. Use --help for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
