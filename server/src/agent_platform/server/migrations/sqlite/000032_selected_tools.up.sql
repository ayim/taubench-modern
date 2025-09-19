ALTER TABLE
  v2_agent
ADD
  COLUMN selected_tools TEXT CHECK (json_valid(selected_tools));