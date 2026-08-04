from aegis.tools import registry


def test_six_crm_tools_registered():
    assert registry.names() == sorted(
        [
            "read_ticket",
            "search_customers",
            "send_email",
            "update_billing",
            "create_refund",
            "delete_customer",
        ]
    )


def test_every_tool_declares_destructiveness():
    for name in registry.names():
        tool = registry.require(name)
        assert tool.destructiveness in {"read", "write", "external", "destructive"}


def test_delete_customer_is_marked_destructive():
    assert registry.require("delete_customer").destructiveness == "destructive"


def test_schema_marks_required_arguments():
    schema = registry.require("create_refund").schema()
    assert set(schema["parameters"]["required"]) == {"customer_id", "amount", "reason"}
