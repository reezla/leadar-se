from __future__ import annotations

import re

import streamlit as st

from lead_finder.use_result_selection import parse_visual_order, table_order_key

_ID = re.compile(r"^[A-Za-z0-9_]+$")
_SCRIPT = """\
<div id="table-order-bridge-__SESSION__" hidden></div>
<script>
(function () {
  var rows = __ROWS__;
  var sessionKey = "__SESSION__";
  var editorSel = '[class*="st-key-__WIDGET__"]';
  var inputSel = '[class*="st-key-table_order_' + sessionKey + '"] input';
  var clusterMark = "st-key-select_cluster_" + sessionKey;
  var slot = window.__leadTableOrder || (window.__leadTableOrder = {});
  var previous = slot[sessionKey];
  if (typeof previous === "function") {
    document.removeEventListener("click", previous, true);
  } else if (previous) {
    document.removeEventListener("click", previous.onClick, true);
    clearInterval(previous.timer);
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

  function inspect(fiber) {
    var perms = [];
    var sorted = false;
    var hook = fiber.memoizedState;
    for (var guard = 0; hook && guard < 300; guard++) {
      var found = asPerm(hook.memoizedState);
      if (found) {
        perms.push(found);
      }
      var state = hook.memoizedState;
      if (state && state.columnId && (state.direction === "asc" || state.direction === "desc")) {
        sorted = true;
      }
      hook = hook.next;
    }
    return {perms: perms, sorted: sorted};
  }

  function readOrder() {
    var root = document.querySelector(editorSel);
    if (!root) {
      return undefined;
    }
    var start = root.querySelector("canvas") || root.querySelector('[data-testid="stDataFrame"]');
    if (!start) {
      return undefined;
    }
    var best = null;
    var saw = false;
    var node = start;
    for (var up = 0; node && up < 14; up++) {
      var fiber = fiberOf(node);
      for (var guard = 0; fiber && guard < 150; guard++) {
        var info = inspect(fiber);
        if (info.sorted || info.perms.length) {
          saw = true;
        }
        if (info.sorted && info.perms.length) {
          return choose(info.perms);
        }
        if (!best && info.perms.length) {
          best = choose(info.perms);
        }
        fiber = fiber.return;
      }
      node = node.parentElement;
    }
    if (best) {
      return best;
    }
    return saw ? null : undefined;
  }

  function commit(json) {
    var input = document.querySelector(inputSel);
    if (!input || input.value === json) {
      return;
    }
    var proto = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
    proto.set.call(input, json);
    var fiber = fiberOf(input);
    var event = {target: {value: json}, currentTarget: input, relatedTarget: null};
    for (var guard = 0; fiber && guard < 12; guard++) {
      var props = fiber.memoizedProps;
      if (props && typeof props.onChange === "function") {
        props.onChange(event);
        if (typeof props.onBlur === "function") {
          props.onBlur(event);
        }
        return;
      }
      fiber = fiber.return;
    }
    input.dispatchEvent(new Event("input", {bubbles: true}));
    input.dispatchEvent(new FocusEvent("focusout", {bubbles: true}));
  }

  var unsortedReads = 0;

  function sync() {
    var order = readOrder();
    if (order === undefined) {
      return;
    }
    if (order === null) {
      unsortedReads += 1;
      if (unsortedReads >= 2) {
        commit("");
      }
      return;
    }
    unsortedReads = 0;
    commit(JSON.stringify(order));
  }

  function onClick(event) {
    var target = event.target;
    if (!target || !target.closest) {
      return;
    }
    var button = target.closest('[class*="st-key-select_more_"] button');
    if (button) {
      var cluster = button.closest('[class*="st-key-select_cluster_"]');
      if (!cluster || cluster.className.indexOf(clusterMark) === -1) {
        return;
      }
      try {
        sync();
      } catch (error) {
        return;
      }
      return;
    }
    var root = document.querySelector(editorSel);
    if (!root || !root.contains(target)) {
      return;
    }
    setTimeout(function () {
      try {
        sync();
      } catch (error) {
        return;
      }
    }, 80);
  }

  var hidden = document.querySelector(inputSel);
  if (hidden) {
    hidden.tabIndex = -1;
  }
  slot[sessionKey] = {onClick: onClick, timer: setInterval(function () {
    try {
      sync();
    } catch (error) {
      return;
    }
  }, 500)};
  document.addEventListener("click", onClick, true);
})();
</script>
"""


def render_table_order_field(session_key: str, row_count: int) -> list[int]:
    raw = st.text_input(
        "Table order",
        key=table_order_key(session_key),
        label_visibility="collapsed",
        live="0ms",
    )
    return parse_visual_order(raw, row_count)


def render_table_order_script(widget_key: str, session_key: str, row_count: int) -> None:
    if row_count <= 0 or not _ID.fullmatch(widget_key) or not _ID.fullmatch(session_key):
        return
    body = (
        _SCRIPT.replace("__ROWS__", str(row_count))
        .replace("__SESSION__", session_key)
        .replace("__WIDGET__", widget_key)
    )
    st.html(body, unsafe_allow_javascript=True)
