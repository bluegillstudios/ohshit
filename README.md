# `ohshit`

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

Requires Python 3 and [colorama](https://pypi.org/project/colorama/).

Install with `pip`:
`pip install colorama`

## Usage

Run from the directory of a Git repository directly. For help:

`ohshit -h`
