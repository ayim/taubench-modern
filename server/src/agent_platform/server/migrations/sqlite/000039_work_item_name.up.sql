update
  v2_work_items
set
  work_item_name = 'Work Item ' || work_item_id
where
  work_item_name is null;