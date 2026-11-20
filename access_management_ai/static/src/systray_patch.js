/** Copyright (C) NexGen Solutions */
/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { NavBar } from "@web/webclient/navbar/navbar";
import { UserMenu } from "@web/webclient/user_menu/user_menu";
import { getAccessManagement, getHiddenSystrayKeys } from "./access_management";

const SWITCH_USER_KEY = "access_management_ai.SwitchUserMenu";

/** Hide systray items listed in the user's profile(s). */
patch(NavBar.prototype, {
    get systrayItems() {
        const hidden = getHiddenSystrayKeys();
        if (!hidden.size) {
            return super.systrayItems;
        }
        // Keep Switch User visible while impersonating so admins can switch back.
        const switchFrom = getAccessManagement().switch_from;
        return super.systrayItems.filter((item) => {
            if (item.key === SWITCH_USER_KEY && switchFrom) {
                return true;
            }
            return !hidden.has(item.key);
        });
    },
});

/** Hide user menu items listed in the user's profile(s). */
patch(UserMenu.prototype, {
    getElements() {
        const elements = super.getElements();
        const hidden = getHiddenSystrayKeys();
        if (!hidden.size) {
            return elements;
        }
        return elements.filter((element) => !hidden.has(element.id));
    },
});
