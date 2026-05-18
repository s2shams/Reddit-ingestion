{% macro get_last_run_date(data_flow_name) %}
    {% if execute %}

        {{ log(
            "Getting last run date for: " ~ data_flow_name,
            info=true
        ) }}

        {% set query %}
            SELECT MAX(etl_datetime)
            FROM `{{ var('proc_status') }}`
            WHERE data_flow_name = '{{ data_flow_name }}'
        {% endset %}

        {% set result = run_query(query) %}
        {% set latest_datetime = result.columns[0].values()[0] %}

        {% if latest_datetime is none %}
            {% do exceptions.warn(
                "Processing status entry for :" ~ data_flow_name ~ " was not found"
            ) %}
        {% else %}
            {{ log(
                "Last run date found for " ~ data_flow_name ~ ": " ~ latest_datetime, info=true
            ) }}
        {% endif %}

        {{ return(latest_datetime) }}

    {% else %}

        {{ log(
            "Skipping execution during parse phase",
            info=true
        ) }}

        {{ return(None) }}
    {% endif %}
{% endmacro %}

{% macro update_proc_status(data_flow_name, etl_datetime, insert_if_missing=false) %}
    {% if execute %}

        {% set current_entry = get_last_run_date(data_flow_name) %}

        {% if current_entry is none %}
            {% do exceptions.warn(
                "The data_flow specified does not exist in processing_status table: " ~ data_flow_name
            ) %}

            {% if insert_if_missing %}
                {{ log(
                    "Inserting data_flow " ~ data_flow_name ~ " into processing_status table with entry: " ~ etl_datetime, info=true
                ) }}

                {% set query %}
                    INSERT INTO `{{ var('proc_status') }}`
                    (
                        data_flow_name,
                        etl_datetime
                    )
                    VALUES
                    (
                        '{{ data_flow_name }}',
                        DATETIME('{{ etl_datetime }}')
                    )
                {% endset %}

                {% do run_query(query) %}

            {% endif %}

        {% else %}
            {{ log(
                "Updating data_flow " ~ data_flow_name ~ " from " ~ current_entry ~ " -> " ~ etl_datetime, info=true
            ) }}

            {% set query %}
                UPDATE `{{ var('proc_status') }}`
                SET etl_datetime = DATETIME('{{ etl_datetime }}')
                WHERE data_flow_name = '{{ data_flow_name }}'
            {% endset %}

            {% do run_query(query) %}

        {% endif %}

    {% else %}

        {{ log(
            "Skipping execution during parse phase",
            info=true
        ) }}

    {% endif %}
{% endmacro %}