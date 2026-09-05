-- Revenue by product category by month.
-- Aggregates fact_orders through dim_products to answer a genuinely
-- common BI question: which categories drive revenue, and how does
-- that trend over time?

select
    dp.category,
    datefromparts(year(fo.order_date), month(fo.order_date), 1) as revenue_month,
    count(distinct fo.order_id)      as order_count,
    sum(fo.quantity)                 as units_sold,
    sum(fo.line_total)               as total_revenue,
    avg(fo.line_total)               as avg_line_value

from dbo.fact_orders fo
inner join dbo.dim_products dp
    on fo.product_key = dp.product_key

group by
    dp.category,
    datefromparts(year(fo.order_date), month(fo.order_date), 1)