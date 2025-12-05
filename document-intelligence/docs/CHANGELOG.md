# Changelog

## Unreleased

## 0.13.1 - 2025-11-27

- Add postgres views when a data model is created

## 0.13.0 - 2025-11-12

- Add document service v2 alpha version
- Exceptions now inherits from `sema4ai.actions.ActionError`
- Update max_output_tokens to `10240` across all prompt generate calls

## 0.12.0 - 2025-11-06

- Query document now returns a Table in case there is only one view
- Bugfixes for parse caching

## 0.11.2 - 2025-10-14

- Fix `start_extract_with_schema` to get the parse job in case job_id is given

## 0.10.0 - 2025-09-30

- Use `gpt-4o` for KB reranking model
- Query KB action now returns the matched chunk
- Add the option to give user prompt to schema generation

## 0.8.2 - 2025-09-18

- Fixed PyPI listing
- Added license info and description

## 0.8.1 - 2025-09-18

- First release to PyPI
