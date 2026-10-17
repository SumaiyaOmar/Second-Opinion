"""One-shot presentation interactions; no data or provider access."""

from uuid import uuid4
import json

import streamlit.components.v1 as components


SCROLL_SCRIPT = '''<script>
(() => {
  const targetId = __TARGET_ID__;
  const requestToken = __REQUEST_TOKEN__;
  let host;
  let doc;
  try {
    host = window.parent;
    doc = host.document;
  } catch (_) {
    return; // Respect any deployment's cross-origin policy.
  }
  host.__secondOpinionScrollToken = requestToken;
  // A previous navbar fragment must not re-anchor a later analysis rerender.
  if (host.location.hash) {
    host.history.replaceState(host.history.state, "", host.location.pathname + host.location.search);
  }
  let observer;
  let timer;
  let finished = false;
  let stableFrames = 0;
  let previousTop;
  const cleanup = () => {
    if (observer) observer.disconnect();
    if (timer) host.clearTimeout(timer);
  };
  const attempt = () => {
    if (finished) return;
    if (host.__secondOpinionScrollToken !== requestToken) {
      finished = true;
      cleanup();
      return;
    }
    const target = doc.getElementById(targetId);
    const card = targetId === "try-it-section" ? doc.querySelector(".st-key-input_card") : target;
    if (!target || !card || !card.getBoundingClientRect().height) return;
    // Wait for the parent app's input layout to settle before one scroll.
    const top = target.getBoundingClientRect().top;
    stableFrames = previousTop !== undefined && Math.abs(top - previousTop) < 1 ? stableFrames + 1 : 0;
    previousTop = top;
    if (stableFrames < 3) {
      host.requestAnimationFrame(attempt);
      return;
    }
    finished = true;
    cleanup();
    if (host.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      target.scrollIntoView({ behavior: "instant", block: "start" });
    } else {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };
  observer = new MutationObserver(attempt);
  observer.observe(doc.body, {childList: true, subtree: true});
  const poll = () => {
    if (finished) return;
    attempt();
    if (!finished) timer = host.setTimeout(poll, 100);
  };
  poll();
  host.setTimeout(() => { finished = true; cleanup(); }, 8000);
})();
</script>'''


SECTION_IDS = {"home-section", "how-it-works-section", "try-it-section", "live-investigation-section",
               "stress-test-section", "benchmark-evidence-section", "about-section", "final-verdict-result-section"}


def scroll_to_section(target):
    if target not in SECTION_IDS:
        raise ValueError("Unknown UI section.")
    token = uuid4().hex
    script = SCROLL_SCRIPT.replace("__TARGET_ID__", json.dumps(target)).replace("__REQUEST_TOKEN__", json.dumps(token))
    components.html(f"<!-- scroll-{token} -->" + script,
                    height=0, width=0, scrolling=False, tab_index=-1)


def scroll_to_inputs():
    scroll_to_section("try-it-section")
