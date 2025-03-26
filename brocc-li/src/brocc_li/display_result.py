from rich.console import Console
from rich.table import Table
from typing import List, Dict, Any, Union, Tuple, Sequence

console = Console()

# Default styles for different types of content
DEFAULT_STYLES = {
    "text": "white",
    "title": "bold white",
    "author": "cyan",
    "date": "yellow",
    "url": "blue",
    "summary": "dim",
    "metrics": "yellow",
}


def display_items(
    items: List[Dict[str, Any]],
    title: str,
    columns: Sequence[Union[str, Tuple[str, str], Tuple[str, str, bool]]],
) -> None:
    """Display items in a rich table with auto-sizing and smart defaults.

    Args:
        items: List of dictionaries containing item data
        title: Title for the table
        columns: List of column definitions. Each can be:
            - str: Column name (uses default style)
            - tuple[str, str]: (name, style)
            - tuple[str, str, bool]: (name, style, no_wrap)
    """
    table = Table(
        title=title,
        show_header=True,
        header_style="bold magenta",
        show_lines=True,
        width=console.width,
    )

    # Add columns with smart defaults
    for col in columns:
        if isinstance(col, str):
            name, style, no_wrap = col, DEFAULT_STYLES.get(col.lower(), "white"), False
        elif len(col) == 2:
            name, style = col
            no_wrap = False
        else:
            name, style, no_wrap = col

        table.add_column(name, style=style, no_wrap=no_wrap)

    for item in items:
        row_data = []
        for col in columns:
            name = col[0] if isinstance(col, (tuple, list)) else col
            value = item.get(name, "")
            row_data.append(str(value) if value is not None else "")

        table.add_row(*row_data)

    console.print(table)
