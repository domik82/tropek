# Coding rules

- **No cryptic variable names.** Never use single-letter or abbreviated variable names like `r`, `cp`, `ev`, `e`, `val`, `stmt`, `subq`, `col`, `res`, `tmp`, `cb`. Name variables after what they represent: `row` not `r`, `change_point` not `cp`, `evaluation` not `ev`. This applies everywhere including list comprehensions and lambdas. Only `i`, `x`, `db`, `id` are acceptable short names.

{
  "permissions": {
    "allow": [
      "Read",
      "Edit",
      "MultiEdit",
      "Bash(bash */scripts/start-server.sh --project-dir *)",
      "Read(*/superpowers/5.0.2/**)",
      "mcp__plugin_playwright_playwright__browser_navigate",
      "mcp__plugin_playwright_playwright__browser_take_screenshot",
      "mcp__plugin_playwright_playwright__browser_snapshot",
      "mcp__plugin_playwright_playwright__browser_run_code",
      "mcp__plugin_playwright_playwright__browser_wait_for",
      "mcp__penpot__execute_code",
      "mcp__penpot__penpot_api_info",
      "mcp__penpot__export_shape",
      "mcp__penpot__high_level_overview",
      "Bash(pnpm exec:*)",
      "Bash(./scripts/ui-test.sh --tail 40)"
    ],
    "deny": [
      "Bash(sudo *)",
      "Bash(wget *)",
      "Bash(ssh *)",
      "Bash(scp *)",
      "Read(.env)",
      "Read(.env.*)",
      "Read(**/secrets/**)",
      "Read(**/.aws/**)",
      "Bash(python *)",
      "Bash(python3 *)"
    ],
    "ask": [
      "Bash(rm *)",
      "Bash(curl *)",
      "Bash(git push *)",
      "Bash(git rebase *)",
      "Bash(git reset *)",
      "Bash(docker run *)"
    ]
  }
}
