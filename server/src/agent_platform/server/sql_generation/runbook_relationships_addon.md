## Using Relationships for Multi-Table Queries

When the semantic data model includes **relationships** metadata, leverage it for accurate JOINs:

### Why Relationships Matter

Relationships define validated connections between tables with:

- **Exact join columns**: Pre-verified column pairs for JOIN conditions
- **Performance optimization**: Relationships are pre-validated and optimized for the data model

### What We Provide

When relationships are available, we will provide you with a list of relationships between tables based on foreign-key constraints that have been defined in the database schema. This information will appear in your initial message or system context.

**Format of Relationship Information:**

Relationships are presented as structured JOIN guidance showing:

- **Table pairs**: Which tables can be joined (e.g., "orders → customers")
- **Join columns**: The exact column pairs to use in the JOIN condition (e.g., "orders.customer_id = customers.id")
- **JOIN syntax**: Ready-to-use SQL JOIN clauses

**Example of provided relationship:**

```
1. orders_customers_fk: orders → customers
   JOIN customers ON orders.customer_id = customers.id
```

This means the `orders` table has a foreign key `customer_id` that references the `id` column in the `customers` table. The relationship name (`orders_customers_fk`) is the foreign key constraint name from the database schema.

**For multi-table queries**, relationships may be chained:

```sql
-- Example using multiple provided relationships:
SELECT p.name, SUM(oi.quantity * oi.price) as revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.id          -- 1. order_items_orders_fk: order_items → orders
JOIN products p ON oi.product_id = p.id            -- 2. order_items_products_fk: order_items → products
GROUP BY p.id, p.name
```

**If relationship information is provided**, prefer using it over inferring join keys from column names, as these relationships are pre-validated and optimized for the data model.

**If no relationship information is provided** for tables you need to join, infer join keys from:

- Column naming patterns (e.g., `table_id` → `table.id`)
- Primary/foreign key conventions
- Use `describe_table` to understand column semantics
- Document your inference as an assumption in your response
