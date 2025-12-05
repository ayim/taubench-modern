# DOCX to Markdown Test Framework

This directory contains test cases for the `docx_to_markdown` functionality.

## Test Case Structure

Each test case should be placed in its own directory following the naming convention `test_case_N` where N is a number.

### Required Files

Each test case directory must contain:

1. **`data.docx`** - The input DOCX file to be converted
2. **`markdown.txt`** - The expected markdown output after conversion

### Directory Structure Example

```
docx_to_markdown/
├── test_case_1/
│   ├── data.docx
│   └── markdown.txt
├── test_case_2/
│   ├── data.docx
│   └── markdown.txt
└── test_case_3/
    ├── data.docx
    └── markdown.txt
```

## How to Add New Test Cases

1. Create a new directory named `test_case_N` (where N is the next available number)
2. Place your DOCX file inside the directory and name it `data.docx`
3. Create the expected markdown output in a file named `markdown.txt`
4. Run the tests - the framework will automatically discover and run your new test case

## Running Tests

To run all docx_to_markdown tests:

```bash
cd libraries/agent-server-client
python -m pytest tests/test_docx_to_markdown.py -v
```

To run a specific test case:

```bash
python -m pytest tests/test_docx_to_markdown.py::TestDocxToMarkdown::test_docx_to_markdown_conversion[test_case_1] -v
```

## Test Framework Features

- **Automatic Discovery**: The framework automatically discovers test cases by scanning directories
- **Dynamic Parameterization**: Uses pytest parametrization to run each test case independently
- **No Code Changes Required**: Just add new test case directories with the required files
- **Clear Error Messages**: Provides detailed output when tests fail, showing both expected and actual results
- **File Validation**: Ensures both required files exist before running tests

## Test Output

When tests pass, you'll see:

```
PASSED tests/test_docx_to_markdown.py::TestDocxToMarkdown::test_docx_to_markdown_conversion[test_case_1]
```

When tests fail, you'll see a detailed comparison showing:

- The test case that failed
- Expected markdown content
- Actual markdown content
- Clear indication of what differs
