from __future__ import annotations

import re

import streamlit as st

from lead_finder.use_company_search import SearchResult
from lead_finder.use_result_selection import original_indices, results_editor_key
from lead_finder.use_table_page import displayed_bounds

_ID = re.compile(r"^[A-Za-z0-9_]+$")
_SCRIPT = """\
<script>
(function () {
  var originals = __INDICES__;
  var rows = __ROWS__;
  var editorSel = '[class*="st-key-__WIDGET__"]';
  if (!originals.length) {
    return;
  }

  function fiberOf(node) {
    if (!node) {
      return null;
    }
    var keys = Object.keys(node);
    for (var i = 0; i < keys.length; i++) {
      if (keys[i].indexOf("__reactFiber$") === 0) {
        return node[keys[i]];
      }
    }
    return null;
  }

  function asPerm(value) {
    var list = value;
    if (Array.isArray(value) && value.length === 2 && Array.isArray(value[0])) {
      list = value[0];
    }
    if (!Array.isArray(list) || list.length !== rows) {
      return null;
    }
    var seen = new Uint8Array(rows);
    for (var i = 0; i < list.length; i++) {
      var n = list[i];
      if (typeof n !== "number" || (n | 0) !== n || n < 0 || n >= rows || seen[n]) {
        return null;
      }
      seen[n] = 1;
    }
    return list;
  }

  function isIdentity(list) {
    for (var i = 0; i < list.length; i++) {
      if (list[i] !== i) {
        return false;
      }
    }
    return true;
  }

  function choose(perms) {
    for (var i = 0; i < perms.length; i++) {
      if (!isIdentity(perms[i])) {
        return perms[i];
      }
    }
    return perms.length ? perms[0] : null;
  }

  function inspect(fiber) {
    var perms = [];
    var grid = null;
    var hook = fiber.memoizedState;
    for (var guard = 0; hook && guard < 300; guard++) {
      var found = asPerm(hook.memoizedState);
      if (found) {
        perms.push(found);
      }
      hook = hook.next;
    }
    var props = fiber.memoizedProps;
    var selection = props && props.gridSelection;
    var canSelect = props && typeof props.onGridSelectionChange === "function";
    if (canSelect && selection && selection.rows && selection.rows.toArray) {
      grid = props;
    }
    return {perms: perms, grid: grid};
  }

  function read() {
    var root = document.querySelector(editorSel);
    if (!root) {
      return null;
    }
    var start = root.querySelector("canvas") || root;
    var perms = [];
    var grid = null;
    var node = start;
    for (var up = 0; node && up < 16; up++) {
      var fiber = fiberOf(node);
      for (var guard = 0; fiber && guard < 200; guard++) {
        var info = inspect(fiber);
        for (var p = 0; p < info.perms.length; p++) {
          perms.push(info.perms[p]);
        }
        if (!grid && info.grid) {
          grid = info.grid;
        }
        fiber = fiber.return;
      }
      node = node.parentElement;
    }
    return {order: choose(perms), grid: grid};
  }

  function visualPositions(order) {
    var place = {};
    for (var i = 0; i < order.length; i++) {
      place[order[i]] = i;
    }
    var positions = [];
    for (var j = 0; j < originals.length; j++) {
      if (place[originals[j]] !== undefined) {
        positions.push(place[originals[j]]);
      }
    }
    return positions;
  }

  function apply(order, grid) {
    var positions = visualPositions(order);
    var rowsSelection = grid.gridSelection.rows;
    var current = rowsSelection.toArray();
    var index;
    for (index = 0; index < current.length; index++) {
      rowsSelection = rowsSelection.remove(current[index]);
    }
    for (index = 0; index < positions.length; index++) {
      rowsSelection = rowsSelection.add(positions[index]);
    }
    grid.onGridSelectionChange({
      rows: rowsSelection,
      columns: grid.gridSelection.columns,
      current: undefined
    });
  }

  var started = Date.now();
  function tick() {
    var found = read();
    if (found && found.grid && found.order) {
      var desired = visualPositions(found.order).join(",");
      var checked = found.grid.gridSelection.rows.toArray().join(",");
      if (desired !== checked) {
        apply(found.order, found.grid);
        return;
      }
    }
    if (Date.now() - started > 800) {
      return;
    }
    requestAnimationFrame(tick);
  }
  tick();
})();
</script>
"""


def render_selection_follow(session_key: str) -> None:
    if not st.session_state.pop(f"{session_key}_follow_selection", None):
        return
    orgs = st.session_state.pop(f"{session_key}_pinned_orgs", None)
    if not isinstance(orgs, list) or not orgs:
        return
    stored = st.session_state.get(session_key)
    if not isinstance(stored, SearchResult):
        return
    start, end = displayed_bounds(st.session_state, session_key, len(stored.companies))
    visible = stored.companies[start:end]
    indices = original_indices(
        [item.company.organization_number for item in visible],
        [str(org) for org in orgs],
    )
    if not indices:
        return
    nonce = int(st.session_state.get(f"{session_key}_nonce", 0) or 0)
    page = int(st.session_state.get(f"{session_key}_page") or 0)
    widget_key = results_editor_key(session_key, nonce, page)
    if not _ID.fullmatch(widget_key):
        return
    body = (
        _SCRIPT.replace("__INDICES__", str(indices))
        .replace("__ROWS__", str(len(visible)))
        .replace("__WIDGET__", widget_key)
    )
    st.html(body, unsafe_allow_javascript=True)
