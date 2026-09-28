-- sp_calculate_rep_incentives.sql
-- Description: Calculates a simple bonus incentive for sales reps based on their sales volume.

CREATE OR REPLACE PROCEDURE catalyst.sp_calculate_rep_incentives()
LANGUAGE plpgsql
AS $$
BEGIN
    -- Create a summary table for rep incentives based on total prescription value
    DROP TABLE IF EXISTS catalyst.rep_incentives_summary;
    
    CREATE TABLE catalyst.rep_incentives_summary AS
    SELECT 
        rep_id,
        SUM(revenue) AS total_revenue,
        CASE 
            WHEN SUM(revenue) > 500000 THEN SUM(revenue) * 0.05
            WHEN SUM(revenue) > 200000 THEN SUM(revenue) * 0.02
            ELSE 0
        END AS incentive_bonus
    FROM 
        catalyst.fct_rx
    GROUP BY 
        rep_id;

    RAISE NOTICE 'Incentives calculated successfully.';
END;
$$;
