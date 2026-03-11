Uses uv. Run tests like this:

uv run pytest

Commit early and often. Commits should bundle the test, implementation, and documentation changes together.

Run Black to format code before you commit:

uv run black .


document any unusual behavior, edge cases, or implementation quirks encountered during script creation. This creates invaluable context for future modifications and debugging sessions.

If you decide to do something with Github Actions, make sure to consult `https://simonw.github.io/actions-latest/versions.txt` to see what the latest versions of packages to use should be. 

Commit fairly often, once you think you finish a single task. This is especially important if you are about to try something desctructive like deleting code or refactoring a file. 

Don't use `git -C ...` Rather use the commands directly.
## Style Guide
General:

1. Don't use comments to split up your files. The function/class names you use should be sufficiently descriptive to not require sections (e.g., # 1. Clean Data). If you find yourself wanting to do this, this is probably a sign you need split your file into multiple files. 
2. Avoid catching exceptions like these where you just raise a very similar exception afterwards.

```
 try:
    return json.loads(json_str)
except json.JSONDecodeError as e:
    raise ValueError(f"Invalid JSON in response: {e}")
```
### Testing
When you are writing unit tests, please do not use classes. If you see you have states you need to keep track with, favor pytest fixtures

## Planning
When creating implementation plans, always save them to your memory directory so they persist across sessions. Write plans to files like `memory/plan-<topic>.md` and link them from `MEMORY.md`.