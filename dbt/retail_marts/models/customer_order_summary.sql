-- Customer-level order summary: total orders, total spend, last order date.
-- Built on top of the Gold star schema (fact_orders + dim_customers).

select
    dc.customer_id,
    dc.first_name,
    dc.last_name,
    dc.city,
    dc.country,
    count(distinct fo.order_id)      as total_orders,
    sum(fo.line_total)               as total_spend,
    max(fo.order_date)               as last_order_date

from dbo.fact_orders fo
inner join dbo.dim_customers dc
    on fo.customer_key = dc.customer_key
    and dc.is_current = 1

group by
    dc.customer_id,
    dc.first_name,
    dc.last_name,
    dc.city,
    dc.country