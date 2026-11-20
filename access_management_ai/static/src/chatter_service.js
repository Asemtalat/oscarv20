/** Copyright (C) NexGen Solutions */
/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/web_portal_project/chatter";
import { getChatterForModel } from "./access_management";
import { useEffect } from "@odoo/owl";

/**
 * Hide chatter sub-features per model (and globally) by toggling marker classes
 * on the chatter root element; the actual hiding is done in access_management_ai.scss.
 */
patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);
        useEffect(() => {
            const el = this.rootRef();
            if (!el) {
                return;
            }
            const cfg = getChatterForModel(this.threadModel());
            el.classList.toggle("o-am-hide-chatter", cfg.hide);
            if (cfg.hide) {
                const container = el.closest(".o-mail-ChatterContainer");
                if (container) {
                    container.classList.add("d-none");
                }
            } else {
                const container = el.closest(".o-mail-ChatterContainer");
                if (container) {
                    container.classList.remove("d-none");
                }
            }
            el.classList.toggle("o-am-hide-send-message", cfg.send_message);
            el.classList.toggle("o-am-hide-log-note", cfg.log_note);
            el.classList.toggle("o-am-hide-activities", cfg.activities);
            el.classList.toggle("o-am-hide-followers", cfg.followers);
            el.classList.toggle("o-am-hide-attachments", cfg.attachments);
            el.classList.toggle("o-am-hide-search-messages", cfg.search);
        });
    },
});
