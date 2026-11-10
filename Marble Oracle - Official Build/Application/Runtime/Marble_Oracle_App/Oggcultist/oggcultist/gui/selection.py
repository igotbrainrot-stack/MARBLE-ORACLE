"""Standard desktop multi-selection for track Treeviews.

Ctrl+A selects every visible row (when the track table has keyboard focus).
Ctrl+click toggles a row; Shift+click selects an anchored range; Ctrl+Shift
+click adds an anchored range. Does not intercept column headers or scrollbars.
"""
from __future__ import annotations


def bind_track_selection(tree):
    """Bind explicit platform-consistent selection and return the callbacks for tests."""
    anchor = [None]

    def select_all(event):
        ids = tree.get_children('')
        if ids:
            tree.selection_set(ids)
        return 'break'

    def click(event, mode):
        item = tree.identify_row(event.y)
        if not item:
            return None   # Allow heading clicks, column resize etc.
        ids = tree.get_children('')
        if item not in ids:
            return None
        tree.focus_set()
        tree.focus(item)
        if mode == 'one':
            tree.selection_set((item,))
            anchor[0] = item
        elif mode == 'toggle':
            if item in tree.selection():
                tree.selection_remove((item,))
                # Keep the previous anchor when deselecting a row.
            else:
                tree.selection_add((item,))
                anchor[0] = item
        else:
            start = anchor[0] if anchor[0] in ids else item
            low, high = sorted((ids.index(start), ids.index(item)))
            selected_range = ids[low:high+1]
            if mode == 'range_add':
                tree.selection_add(selected_range)
            else:
                tree.selection_set(selected_range)
        tree.see(item)
        return 'break'

    tree.bind('<Control-a>', select_all)
    tree.bind('<Control-A>', select_all)
    # Bind the most specific pattern so Ctrl+Shift cannot be treated as plain Ctrl.
    tree.bind('<Control-Shift-Button-1>', lambda event: click(event, 'range_add'))
    tree.bind('<Control-Button-1>', lambda event: click(event, 'toggle'))
    tree.bind('<Shift-Button-1>', lambda event: click(event, 'range'))
    tree.bind('<Button-1>', lambda event: click(event, 'one'))
    return select_all, click
