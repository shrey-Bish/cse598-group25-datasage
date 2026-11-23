"""Tests for cleaning recipes (datasage/recipes.py). Synthetic data only; no API key or network."""

import hashlib
import json

import pandas as pd
import pytest

from datasage import recipes

MONTH1 = (
    "Order_ID,Date,Category,Quantity,Price\n"
    "1,2026-08-01,Electronics,2,$10.00\n"
    "2,2026-08-02,electronics,1,$5.00\n"
    "3,2026-08-03,Accessories,3,$7.50\n"
)
RULES = '{"Category": {"allowed": ["Electronics", "Accessories"]}}\n'


@pytest.fixture
def month1(tmp_path):
    path = tmp_path / "month1.csv"
    path.write_text(MONTH1)
    return path


@pytest.fixture
def rules(tmp_path):
    path = tmp_path / "rules" / "sales_rules.json"
    path.parent.mkdir()
    path.write_text(RULES)
    return path


def _recipe(path, rules_path=None):
    source, schema = recipes.describe_input(path)
    return recipes.Recipe(
        source=source,
        schema=schema,
        rules=recipes.rules_ref(rules_path),
        steps=[
            recipes.Step(fix="normalize_labels", args={"column": "Category", "mapping": {"electronics": "Electronics"}},
                         risk="low", approved_by="auto", portable=True),
            recipes.Step(fix="exclude_rows", args={"rows": [2]}, risk="high", approved_by="approved", portable=False),
        ],
    )


def test_save_and_load_round_trip(tmp_path, month1, rules):
    recipe = _recipe(month1, rules)
    path = recipes.save_recipe(recipe, tmp_path / "recipe.json")

    assert recipes.load_recipe(path) == recipe
    data = json.loads(path.read_text())
    assert data["recipe_version"] == 1
    assert data["source"] == {"name": "month1.csv", "sha256": hashlib.sha256(MONTH1.encode()).hexdigest(), "rows": 3}
    assert data["rules"] == {"name": "sales_rules.json", "sha256": hashlib.sha256(RULES.encode()).hexdigest()}
    assert str(tmp_path) not in path.read_text()  # file names only, no local folders
    # Schema of the raw input as load_table reads it: "$10.00" keeps Price as text.
    assert data["schema"]["columns"] == ["Order_ID", "Date", "Category", "Quantity", "Price"]
    assert data["schema"]["dtypes"] == {"Order_ID": "number", "Date": "text", "Category": "text",
                                        "Quantity": "number", "Price": "text"}


def test_recipe_without_rules_file(tmp_path, month1):
    path = recipes.save_recipe(_recipe(month1), tmp_path / "recipe.json")
    assert json.loads(path.read_text())["rules"] is None
    assert recipes.load_recipe(path).rules is None


def test_fingerprint_ignores_column_order_but_not_names_or_kinds():
    df = pd.DataFrame({"x": [1, 2], "y": ["a", "b"]})
    assert recipes.schema_fingerprint(df) == recipes.schema_fingerprint(df[["y", "x"]])
    assert recipes.schema_fingerprint(df) != recipes.schema_fingerprint(df.rename(columns={"x": "z"}))
    assert recipes.schema_fingerprint(df) != recipes.schema_fingerprint(df.astype({"x": str}))


def test_load_refuses_unknown_version_and_broken_files(tmp_path, month1):
    path = recipes.save_recipe(_recipe(month1), tmp_path / "recipe.json")
    data = json.loads(path.read_text())

    path.write_text(json.dumps({**data, "recipe_version": 2}))
    with pytest.raises(ValueError, match="recipe_version 2"):
        recipes.load_recipe(path)

    del data["schema"]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="not a valid recipe"):
        recipes.load_recipe(path)


# R6: schema check before a replay

def test_check_schema_accepts_the_same_columns_in_any_order(month1):
    recipe = _recipe(month1)
    df = recipes._ds_load_table(month1)
    result = recipes.check_schema(recipe, df[list(reversed(df.columns))])
    assert result == ([], [], {})
    assert result.ok and result.warnings() == []


def test_check_schema_missing_column_blocks_replay(month1):
    result = recipes.check_schema(_recipe(month1), recipes._ds_load_table(month1).drop(columns=["Category"]))
    missing, extra, type_changed = result
    assert (missing, extra, type_changed) == (["Category"], [], {})
    assert not result.ok


def test_check_schema_extra_column_and_type_change_are_warnings(tmp_path, month1):
    recipe = _recipe(month1)
    feb = tmp_path / "month2.csv"
    # Quantity now holds text ("two"), and a new Region column appears.
    feb.write_text("Order_ID,Date,Category,Quantity,Price,Region\n4,2026-09-01,Electronics,two,$1.00,West\n")
    result = recipes.check_schema(recipe, recipes._ds_load_table(feb))
    assert result.missing == []
    assert result.extra == ["Region"]
    assert result.type_changed == {"Quantity": ("number", "text")}
    assert result.ok
    assert result.warnings() == ["extra column 'Region' is not in the recipe; it is left as it is",
                                 "column 'Quantity' was number in the recipe's input and is text here"]
