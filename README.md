# ohshit

A quick CLI tool to help you undo mistakes immediately after a Git commit.  

## Features

- Undo last pushed commit with confirmation  
- Undo last local commit  
- Force push current branch  
- Delete local branches  
- Remove Git remotes  
- Show quick Git status summary  
- Supports `--yes` / `--force` flags to skip confirmation  
- `--dry-run` option to preview commands  
- **Passively detects if run inside a Git repository**  

## Installation

Requires Python 3 and [colorama](https://pypi.org/project/colorama/):
Install with `pip`:
`pip install colorama`

## Usage

Run from the directory of a Git repository directly. 
Here are the options:
```
ohshit              # Undo last pushed commit (default)
ohshit commit       # Undo last local commit
ohshit push         # Force push current branch
ohshit branch <name>  # Delete a local branch
ohshit remote <name>  # Remove a Git remote
ohshit status       # Show Git status summary
ohshit --version    # Show version
```
Use `-y` or `-f` to auto-confirm prompts and `--dry-run` to preview commands without executing.
If run outside a Git repository, ohshit will exit with an error.
