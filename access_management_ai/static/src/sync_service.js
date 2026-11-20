/** Copyright (C) NexGen Solutions */
/** @odoo-module */

import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { user } from "@web/core/user";
import { ORM } from "@web/core/orm_plugin";
import { patch } from "@web/core/utils/patch";

// Odoo 20 can return yesterday's get_views result from its persistent disk
// cache while refreshing it in the background. Profile fields and schedules
// affect the architecture, so a page reload must obtain current views. Keep
// in-page caching, but never reuse view architectures across page loads.
patch(ORM.prototype, {
    call(model, method, args = [], kwargs = {}) {
        const caller = method === "get_views" && this._cache
            ? this.cache({ ...this._cache, type: "ram" })
            : this;
        return super.call.call(caller, model, method, args, kwargs);
    },
});

export const accessManagementSyncService = {
    dependencies: ["orm"],
    async start(env, { orm }) {
        if (!user.userId) return;
        try {
            const result = await orm.call("res.users", "get_access_restrictions", []);
            if (result) {
                // Keep session-only impersonation metadata supplied by ir.http.
                session.access_management_ai = { ...session.access_management_ai, ...result };
            }
        } catch (e) {
            // fail silently if offline or session expired
            console.warn("Failed to sync access management rules on startup", e);
        }
    }
};

// Add this service to run early. Using sequence 1 or similar if needed.
registry.category("services").add("access_management_sync", accessManagementSyncService);
