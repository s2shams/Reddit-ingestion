{% macro generate_schema_name(custom_schema_name, node) %}
    {%- set folder_name = node.fqn[1] -%}
    {{ folder_name }}
{% endmacro %}