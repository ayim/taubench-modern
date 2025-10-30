update
  v2.work_items
set
  work_item_name = 'Work Item ' || work_item_id::text
where
  work_item_name is null;
