# This file exists to allow for ignoring workroom ONLY in the situation
# where prettier is being executed using Make. Within VSCode and other
# editors, we want workroom to remain unignored as otherwise prettier
# will simply fail to work. Whilst running the CLI however we need to
# properly configure the boundary between the workroom formatting and
# the rest of the project, as prettier doesn't support nested
# .prettierignore files.

workroom/**
