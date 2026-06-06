$stdin = [Console]::In.ReadToEnd()
try {
    $j = $stdin | ConvertFrom-Json
    $f = $j.tool_input.file_path
    if ($f -match '\.py$') {
        ruff format $f 2>$null
    }
} catch {}
