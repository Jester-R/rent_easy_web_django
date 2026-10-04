/*!
 * RentEasy Web — app.js
 * Progressive enhancement layer built on jQuery 4 (slim).
 * Every feature here degrades gracefully: without JS the server-rendered
 * forms and links still work.
 */
(function ($) {
  "use strict";

  var RE = window.RentEasy || {};
  RE.urls = RE.urls || {};

  /* ======================================================================
     Toast helper
     ====================================================================== */
  function toast(message, level) {
    var root = document.getElementById("modal-root");
    if (!root) return;
    var icons = { success: "check-circle", error: "alert", info: "info" };
    var icon = icons[level] || "info";
    var el = document.createElement("div");
    el.className = "toast toast-" + (level || "info");
    el.setAttribute("data-flash", "");
    el.style.marginBottom = "0.5rem";
    el.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" ' +
      'stroke-linecap="round" stroke-linejoin="round" width="18" height="18"><circle cx="12" cy="12" r="9"/>' +
      '<path d="M12 11v5.5M12 7.8h.01"/></svg><span class="flex-1"></span>' +
      '<button type="button" data-flash-dismiss class="btn btn-ghost btn-xs -my-1 px-1.5">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" ' +
      'stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><path d="m6 6 12 12M18 6 6 18"/></svg></button>';
    el.querySelector("span").textContent = message;
    if (icon === "check-circle") {
      el.querySelector("svg path").setAttribute("d", "m8 12.3 2.7 2.7L16 9.5");
    } else if (icon === "alert") {
      el.querySelector("svg path").setAttribute(
        "d",
        "M10.7 3.9 2.6 17.5A1.5 1.5 0 0 0 3.9 19.8h16.2a1.5 1.5 0 0 0 1.3-2.3L13.3 3.9a1.5 1.5 0 0 0-2.6 0ZM12 9v4.2M12 16.4h.01"
      );
    }
    root.appendChild(el);
    bindFlashDismiss(el);
    window.setTimeout(function () {
      el.remove();
    }, 5200);
  }
  RE.toast = toast;

  function bindFlashDismiss(scope) {
    $(scope).find("[data-flash-dismiss]").on("click", function () {
      var box = this.closest("[data-flash]");
      if (box) box.remove();
    });
  }

  /* ======================================================================
     Dropdowns (sidebar user menu, language, notifications bell)
     ====================================================================== */
  function closeDropdowns(except) {
    $("[data-dropdown-panel]").each(function () {
      if (this !== except) $(this).addClass("hidden");
    });
    $("[data-dropdown-toggle]").attr("aria-expanded", "false");
  }

  $(document).on("click", "[data-dropdown-toggle]", function (e) {
    e.stopPropagation();
    var wrap = this.closest("[data-dropdown]");
    var panel = wrap ? wrap.querySelector("[data-dropdown-panel]") : null;
    if (!panel) return;
    var willOpen = panel.classList.contains("hidden");
    closeDropdowns(panel);
    panel.classList.toggle("hidden", !willOpen);
    $(this).attr("aria-expanded", willOpen ? "true" : "false");
  });

  $(document).on("click", function (e) {
    if (!$(e.target).closest("[data-dropdown]").length) closeDropdowns(null);
  });

  $(document).on("keydown", function (e) {
    if (e.key === "Escape") {
      closeDropdowns(null);
      closeModal();
    }
  });

  /* ======================================================================
     Modal (confirm dialogs built server-side as <template data-modal>)
     ====================================================================== */
  var activeModal = null;

  function openModal(html) {
    closeModal();
    var root = document.getElementById("modal-root");
    var backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.setAttribute("data-modal-backdrop", "");
    backdrop.innerHTML = html;
    root.appendChild(backdrop);
    document.body.style.overflow = "hidden";
    activeModal = backdrop;
    bindModal(backdrop);
    var focusable = backdrop.querySelector("input, select, textarea, button");
    if (focusable) focusable.focus();
    return backdrop;
  }

  function closeModal() {
    if (!activeModal) return;
    activeModal.remove();
    activeModal = null;
    document.body.style.overflow = "";
  }

  function bindModal(scope) {
    $(scope)
      .on("click", "[data-modal-close]", function () {
        closeModal();
      })
      .on("click", "[data-modal-backdrop]", function (e) {
        if (e.target === this) closeModal();
      });
    // jQuery-driven validation inside modals
    $(scope).find("form[data-validate]").on("submit", function () {
      return validateForm(this);
    });
  }
  RE.openModal = openModal;
  RE.closeModal = closeModal;

  /* Build a confirmation dialog and POST the named form on confirm. */
  function confirmDialog(opts) {
    var body =
      '<div class="modal-panel max-w-md">' +
      '  <div class="flex items-start gap-3 border-b border-hairline px-5 py-4">' +
      '    <span class="grid h-10 w-10 shrink-0 place-items-center rounded-xl ' +
      (opts.tone === "danger" ? "bg-pill-rejected text-danger" : "bg-primary-soft text-primary-dark") + '">' +
      '      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" ' +
      '      stroke-linejoin="round" width="20" height="20"><circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.8h.01"/></svg>' +
      "    </span>" +
      '    <div class="min-w-0"><h3 class="text-[15px] font-extrabold leading-snug"></h3>' +
      '    <p class="mt-1 text-[13px] leading-relaxed text-ink-3"></p></div>' +
      "  </div>" +
      '  <div class="flex flex-col-reverse gap-2 p-4 sm:flex-row sm:justify-end">' +
      '    <button type="button" class="btn btn-outline" data-modal-close></button>' +
      '    <button type="button" class="btn ' +
      (opts.tone === "danger" ? "btn-danger" : "btn-primary") +
      '" data-confirm-yes></button>' +
      "  </div>" +
      "</div>";
    var backdrop = openModal(body);
    backdrop.querySelector("h3").textContent = opts.title || "";
    backdrop.querySelector("p").textContent = opts.body || "";
    backdrop.querySelector("[data-modal-close]").textContent = opts.cancelLabel || "Cancel";
    backdrop.querySelector("[data-confirm-yes]").textContent = opts.confirmLabel || "Confirm";
    backdrop.querySelector("[data-confirm-yes]").on("click", function () {
      closeModal();
      if (opts.onConfirm) opts.onConfirm();
    });
    return backdrop;
  }
  RE.confirmDialog = confirmDialog;

  /* Confirm-then-submit: <button data-confirm-title data-confirm-body ...> */
  $(document).on("click", "[data-confirm]", function (e) {
    e.preventDefault();
    var btn = this;
    var scope = btn.closest("[data-bulk-scope]");
    var form = btn.form || (scope ? scope.querySelector("form[data-bulk-form]") : null);

    var confirmDialog({
      title: btn.getAttribute("data-confirm-title") || "",
      body: btn.getAttribute("data-confirm-body") || "",
      confirmLabel: btn.getAttribute("data-confirm-label") || "OK",
      cancelLabel: btn.getAttribute("data-confirm-cancel") || "Cancel",
      tone: btn.getAttribute("data-confirm-tone") || "primary",
      onConfirm: function () {
        if (!form) return;
        if (btn.form) {
          var name = btn.getAttribute("name");
          if (name) {
            var submitter = document.createElement("input");
            submitter.type = "hidden";
            submitter.name = name;
            submitter.value = btn.getAttribute("value") || "";
            form.appendChild(submitter);
          }
        }
        var next = btn.getAttribute("data-next");
        if (next && !form.querySelector('input[name="next"]')) {
          var hidden = document.createElement("input");
          hidden.type = "hidden";
          hidden.name = "next";
          hidden.value = next;
          form.appendChild(hidden);
        }
        if (typeof form.requestSubmit === "function") form.requestSubmit();
        else form.submit();
      },
    });
  });

  /* ======================================================================
     Password visibility toggles
     ====================================================================== */
  $(document).on("click", "[data-password-toggle]", function () {
    var input = this.parentNode.querySelector("input");
    if (!input) return;
    var isPassword = input.type === "password";
    input.type = isPassword ? "text" : "password";
    this.setAttribute("aria-label", isPassword ? "Hide password" : "Show password");
  });

  /* ======================================================================
     Client-side form validation (mirrors the app's Validators)
     ====================================================================== */
  var USERNAME_RE = /^[A-Za-z0-9._-]{3,30}$/;

  function validateForm(form) {
    var ok = true;
    var firstBad = null;
    $(form)
      .find("input[required], textarea[required], select[required]")
      .each(function () {
        var el = $(this);
        var val = (el.val() || "").trim();
        var bad = !val;
        var type = el.attr("type");
        if (!bad && type === "email") bad = !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val);
        if (!bad && el.attr("name") === "username" && val.indexOf("@") !== -1) bad = true;
        if (!bad && el.attr("name") === "username" && !USERNAME_RE.test(val)) bad = true;
        el.attr("aria-invalid", bad ? "true" : "false");
        if (bad) {
          ok = false;
          if (!firstBad) firstBad = this;
        }
      });

    var pw = form.querySelector('input[name="password"]');
    var pw2 = form.querySelector('input[name="password_confirm"]');
    if (pw && pw2 && pw.value !== pw2.value) {
      $(pw2).attr("aria-invalid", "true");
      ok = false;
      if (!firstBad) firstBad = pw2;
    }

    // submit button busy state
    if (ok) {
      var submit = form.querySelector('button[type="submit"]');
      if (submit) {
        submit.setAttribute("data-busy", "1");
        submit.disabled = true;
        var label = submit.querySelector("[data-btn-label]") || submit;
        if (label.dataset.idle) label.textContent = label.dataset.idle;
        else {
          label.dataset.idle = label.textContent.trim();
          label.textContent = (RE.strings && RE.strings.loading) || "…";
        }
        window.setTimeout(function () {
          submit.disabled = false;
          submit.removeAttribute("data-busy");
        }, 8000);
      }
    } else if (firstBad) {
      firstBad.focus();
      firstBad.scrollIntoView({ block: "center", behavior: "smooth" });
    }
    return ok;
  }
  RE.validateForm = validateForm;

  $(document).on("submit", "form[data-validate]", function (e) {
    if (!validateForm(this)) e.preventDefault();
  });

  /* Live-clear invalid state on input */
  $(document).on("input change", "form[data-validate] .form-input", function () {
    $(this).removeAttr("aria-invalid");
  });

  /* ======================================================================
     Notifications bell — lazy load + badge refresh
     ====================================================================== */
  var bell = $("[data-notifications]");
  if (bell.length) {
    var list = bell.find("[data-bell-list]");
    var loaded = false;

    var paint = function (items) {
      if (!items.length) {
        list.html(
          '<div class="empty-state !py-10">' +
            '<span class="empty-state-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
            'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" width="26" height="26">' +
            '<path d="M18 15.5V10a6 6 0 1 0-12 0v5.5L4 18h16l-2-2.5Z"/><path d="M9.5 21h5"/></svg></span>' +
            "<p></p><p class='!text-[12px]'></p></div>"
        );
        list.find("p").eq(0).text(RE.strings.noNotifications || "");
        list.find("p").eq(1).text(RE.strings.noNotificationsBody || "");
        return;
      }
      var html = items
        .map(function (item) {
          var unread = item.read ? "" : "bg-primary";
          return (
            '<a href="' +
            escapeAttr(item.link || "#") +
            '" class="flex gap-3 rounded-xl p-2.5 transition-colors hover:bg-surface-2">' +
            '<span class="mt-1.5 h-2 w-2 shrink-0 rounded-full ' +
            (item.read ? "bg-transparent" : unread) +
            '"></span>' +
            '<span class="min-w-0 flex-1">' +
            '<span class="block text-[13px] font-bold leading-snug"></span>' +
            '<span class="mt-0.5 block text-[12px] leading-snug text-ink-3"></span>' +
            '<span class="mt-1 block text-[11px] text-ink-3"></span>' +
            "</span></a>"
          );
        })
        .join("");
      list.html(html);
      list.find("a").each(function (i) {
        var item = items[i];
        $(this).find("span").eq(1).text(translate(item.title, item.params));
        $(this).find("span").eq(2).text(translate(item.body, item.params));
        $(this).find("span").eq(3).text(item.created_at ? formatTime(item.created_at) : "");
      });
    };

    var loadBell = function () {
      if (loaded || !RE.urls.notificationsPreview) return;
      loaded = true;
      $.getJSON(RE.urls.notificationsPreview)
        .done(function (data) {
          paint(data.items || []);
          var badge = $("[data-bell-badge]");
          if (!badge) return;
          if (data.unread > 0) {
            badge.text(data.unread > 99 ? "99+" : data.unread).removeClass("hidden");
          } else {
            badge.addClass("hidden");
          }
        })
        .fail(function () {
          loaded = false;
          list.html('<p class="px-4 py-8 text-center text-[13px] text-ink-3">' + (RE.strings.loading || "") + "</p>");
        });
    };

    $(document).on("click", "[data-notifications] [data-dropdown-toggle]", loadBell);
    $(document).on("mouseenter", "[data-notifications]", loadBell);
  }

  function escapeAttr(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  /* Translate a catalogue key on the client using the injected catalogue. */
  function translate(key, params) {
    var cat = RE.catalog || {};
    var entry = cat[key];
    if (!entry) return key;
    var isKhmer = (RE.lang || "en") === "km";
    var text = isKhmer ? entry[1] : entry[0];
    if (params) {
      Object.keys(params).forEach(function (k) {
        text = text.replace(new RegExp("\\{" + k + "\\}", "g"), params[k] == null ? "" : String(params[k]));
      });
    }
    return text;
  }

  function formatTime(iso) {
    try {
      var d = new Date(iso);
      var h = d.getHours();
      var suffix = h >= 12 ? "PM" : "AM";
      var hh = h % 12 || 12;
      var mm = ("0" + d.getMinutes()).slice(-2);
      return (
        ("0" + d.getDate()).slice(-2) +
        " " +
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][d.getMonth()] +
        " " +
        d.getFullYear() +
        ", " +
        hh +
        ":" +
        mm +
        " " +
        suffix
      );
    } catch (e) {
      return "";
    }
  }

  /* Radio chips (lease length, role picker) keep the .is-active highlight. */
  function syncRadioChips(scope) {
    scope.find("input[type=radio][data-lease-radio], input[type=radio][data-chip-radio]").each(function () {
      var chip = this.closest(".chip");
      if (chip) chip.classList.toggle("is-active", this.checked);
    });
  }
  $(document).on("change", "input[type=radio][data-lease-radio], input[type=radio][data-chip-radio]", function () {
    syncRadioChips($(this).closest("form, fieldset, [data-radio-group]").length
      ? $(this).closest("form, fieldset, [data-radio-group]")
      : $(document));
  });
  $(syncRadioChips($(document)));

  /* ======================================================================
     Favicon toggle (AJAX)
     ====================================================================== */
  $(document).on("click", "[data-favorite-toggle]", function (e) {
    e.preventDefault();
    e.stopPropagation();
    var btn = $(this);
    if (btn.data("busy")) return;
    btn.data("busy", 1);
    $.post(btn.attr("href"), { next: window.location.pathname + window.location.search })
      .done(function (data) {
        var on = typeof data === "object" && data.favorited;
        var card = btn.closest("[data-property-id]");
        if (card && typeof data === "object") card.attr("data-favorited", on ? "1" : "0");
        btn.toggleClass("text-primary", !!on).toggleClass("text-ink-3", !on);
        if (on) {
          toast(RE.strings.addedFavorite || "", "success");
        } else if (card && !btn.attr("data-keep-on-screen")) {
          // Remove from favourites list
          window.setTimeout(function () {
            var wrap = card.closest("[data-favorites-list]");
            if (wrap) {
              card.slideUp(160, function () {
                card.remove();
                var left = wrap.find("[data-property-id]").length;
                var empty = document.getElementById("favorites-empty");
                if (left === 0 && empty) empty.classList.remove("hidden");
              });
            }
          }, 60);
        }
      })
      .fail(function () {
        toast(RE.strings.errorGeneric || "Error", "error");
      })
      .always(function () {
        btn.data("busy", 0);
      });
  });

  /* ======================================================================
     Auto-submit filter forms (chips, selects, sliders)
     ====================================================================== */
  $(document).on("click", "[data-auto-submit]", function () {
    var form = this.form || $(this).closest("form");
    if (form) form.submit();
  });

  var debounceTimer = null;
  $(document).on("input", "[data-auto-submit-debounce]", function () {
    var form = this.form;
    if (!form) return;
    window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(function () {
      form.submit();
    }, 550);
  });

  /* ======================================================================
     Bulk selection tables (superadmin console)
     ====================================================================== */
  function syncBulk(scope) {
    var boxes = scope.find("tbody input[data-bulk-item]");
    var checked = scope.find("tbody input[data-bulk-item]:checked");
    var all = boxes.length > 0 && checked.length === boxes.length;
    scope.find("[data-bulk-all]").prop("checked", all);
    var bar = scope.find("[data-bulk-bar]");
    var n = checked.length;
    if (bar && bar.length) {
      bar.toggleClass("hidden", n === 0);
      scope.find("[data-bulk-count]").text(n);
    }
    scope.find("tbody tr").each(function () {
      $(this).toggleClass("is-selected", $("input[data-bulk-item]", this).prop("checked"));
    });
  }

  $(document).on("change", "[data-bulk-item], [data-bulk-all]", function () {
    var scope = $(this).closest("[data-bulk-scope]");
    if (!scope.length) return;
    if ($(this).is("[data-bulk-all]")) {
      scope.find("tbody input[data-bulk-item]").prop("checked", this.checked);
    }
    syncBulk(scope);
  });

  $(document).on("click", "[data-bulk-clear]", function () {
    var scope = $(this).closest("[data-bulk-scope]");
    scope.find("input[data-bulk-item], [data-bulk-all]").prop("checked", false);
    syncBulk(scope);
  });

  /* ======================================================================
     Deep-link focus pulse (notification -> record)
     ====================================================================== */
  $(function () {
    var target = document.querySelector("[data-focus-id]");
    if (!target) return;
    target.classList.add("focus-pulse");
    target.scrollIntoView({ block: "center", behavior: "smooth" });
    window.setTimeout(function () {
      target.classList.remove("focus-pulse");
    }, 3800);
  });

  /* ======================================================================
     Tab panels (console "More" style sections, profile tabs)
     ====================================================================== */
  $(document).on("click", "[data-tab]", function () {
    var name = this.getAttribute("data-tab");
    var group = this.closest("[data-tab-group]");
    if (!group) return;
    $(group).find("[data-tab]").each(function () {
      var on = this.getAttribute("data-tab") === name;
      $(this).toggleClass("is-active", on);
      this.setAttribute("aria-selected", on ? "true" : "false");
    });
    $(group)
      .find("[data-tab-panel]")
      .each(function () {
        $(this).toggleClass("hidden", this.getAttribute("data-tab-panel") !== name);
      });
    var url = this.getAttribute("data-tab-url");
    if (url) window.history.replaceState({}, "", url);
  });

  /* ======================================================================
     Filter sheet / drawer (renter property filters)
     ====================================================================== */
  var sheet = {
    open: function (trigger) {
      var el = document.getElementById(trigger.getAttribute("data-sheet"));
      if (!el) return;
      el.classList.remove("hidden");
      document.body.style.overflow = "hidden";
      el.removeAttribute("aria-hidden");
    },
    close: function (el) {
      var target = el || document.querySelector("[data-sheet]:not(.hidden)");
      if (!target) {
        document.body.style.overflow = "";
        return;
      }
      target.classList.add("hidden");
      target.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
    },
  };
  RE.sheet = sheet;

  $(document).on("click", "[data-sheet-open]", function () {
    sheet.open(this);
  });
  $(document).on("click", "[data-sheet-close]", function () {
    sheet.close(this.closest("[data-sheet]"));
  });
  $(document).on("click", "[data-sheet-backdrop]", function (e) {
    if (e.target === this) sheet.close(this);
  });

  /* Live price output for sliders */
  $(document).on("input", "input[type=range][data-output]", function () {
    var out = document.getElementById(this.getAttribute("data-output"));
    if (out) out.textContent = "$" + Math.round(this.value).toLocaleString();
  });

  /* ======================================================================
     Active mobile nav highlight
     ====================================================================== */
  (function () {
    var path = window.location.pathname;
    var best = null;
    $("[data-nav]").each(function () {
      var href = this.getAttribute("href");
      if (!href || href === "/") return;
      if (path.indexOf(href) === 0) {
        if (!best || href.length > best.getAttribute("href").length) best = this;
      }
    });
    if (best) {
      $(best).addClass("text-primary");
      best.classList.remove("text-ink-2");
    }
    var profile = $("[data-nav='profile']");
    if (!best && profile && path.indexOf("/auth/preferences") === 0) profile.addClass("text-primary");
  })();

  /* ======================================================================
     Boot flash dismissal
     ====================================================================== */
  bindFlashDismiss(document);
  $(function () {
    $("[data-flash]").each(function () {
      var el = this;
      window.setTimeout(function () {
        el.remove();
      }, 6000);
    });
  });

  /* ======================================================================
     Copy-to-clipboard for record IDs
     ====================================================================== */
  $(document).on("click", "[data-copy]", function (e) {
    e.preventDefault();
    var text = this.getAttribute("data-copy");
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(function () {
        toast(RE.strings.copied || text, "success");
      });
    }
  });

  window.RentEasy = RE;
})(jQuery);
