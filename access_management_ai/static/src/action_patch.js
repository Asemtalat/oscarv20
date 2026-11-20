/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActionMenus } from "@web/search/action_menus/action_menus";
import { registry } from "@web/core/registry";
import { getModelRestrictions } from "./access_management";

// Some Odoo 20 Enterprise cog items still read env.isSmall. Odoo now throws
// on that property, which rejects the entire menu's visibility calculation
// and hides unrelated items such as Import. Adapt only the predicate env;
// all native visibility and access checks still run unchanged.
const cogMenuRegistry = registry.category("cogMenu");
const adaptedItems = new WeakSet();
function adaptMenuItem(item) {
    if (!item.isDisplayed || adaptedItems.has(item)) return;
    const isDisplayed = item.isDisplayed;
    item.isDisplayed = function (env) {
        const compatibleEnv = Object.create(env);
        Object.defineProperty(compatibleEnv, "isSmall", {
            get: () => env.services.ui.isSmall,
        });
        return isDisplayed.call(this, compatibleEnv);
    };
    adaptedItems.add(item);
}
for (const item of cogMenuRegistry.getAll()) adaptMenuItem(item);
patch(cogMenuRegistry, {
    add(key, item, options) {
        adaptMenuItem(item);
        return super.add(key, item, options);
    },
});

patch(ActionMenus.prototype, {
    async getActionItems(props) {
        const restrictions = getModelRestrictions(props.resModel);
        if (restrictions.hide_action) {
            return [];
        }
        return super.getActionItems(props);
    }
});
