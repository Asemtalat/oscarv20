/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { Component, proxy, onWillDestroy } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { getAccessManagement } from "./access_management";
import { rpc } from "@web/core/network/rpc";

async function switchUser(userId, userName) {
    if (!confirm(`${_t("Switch your session to")} ${userName || _t("this user")}?`)) return;
    await rpc(`/access_management/login_as/${userId}`, {});
    window.location.href = "/odoo";
}

registry.category("actions").add("access_management_switch_user", async (env, action) => {
    await switchUser(action.params.user_id, action.params.user_name);
});

export class SwitchUserMenu extends Component {
    static template = "access_management_ai.SwitchUserMenu";
    static components = { Dropdown, DropdownItem };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dropdown = useDropdownState();
        this.state = proxy({
            search: "",
            loading: false,
            users: [],
        });
        this._searchTimer = null;
        this._loadSequence = 0;
        onWillDestroy(() => {
            clearTimeout(this._searchTimer);
            this._loadSequence++;
        });
    }

    get am() {
        return getAccessManagement();
    }

    get canSearchUsers() {
        return Boolean(this.am.is_access_admin);
    }

    get switchFrom() {
        return this.am.switch_from || null;
    }

    get buttonTitle() {
        if (this.switchFrom) {
            const name = this.switchFrom.name || this.switchFrom.login || "";
            return name
                ? `${_t("Switch User")} — ${_t("switched from")} ${name}`
                : _t("Switch User — currently impersonating another user");
        }
        return _t("Switch User");
    }

    get currentUserName() {
        return user.name;
    }

    async onBeforeOpen() {
        if (this.canSearchUsers) {
            await this.loadUsers();
        }
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value || "";
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.loadUsers(), 250);
    }

    async loadUsers() {
        if (!this.canSearchUsers) {
            return;
        }
        this.state.loading = true;
        const sequence = ++this._loadSequence;
        try {
            const users = await this.orm.call(
                "res.users",
                "am_search_switchable_users",
                [this.state.search, 25]
            );
            if (sequence === this._loadSequence) {
                this.state.users = users;
            }
        } catch (error) {
            if (sequence !== this._loadSequence) return;
            this.state.users = [];
            this.notification.add(_t("Unable to load users."), { type: "danger" });
        } finally {
            if (sequence === this._loadSequence) this.state.loading = false;
        }
    }

    switchToUser(userId, userName) {
        return switchUser(userId, userName);
    }

    async switchBack() {
        const name = this.switchFrom?.name || _t("your account");
        if (!confirm(`${_t("Switch back to")} ${name}?`)) {
            return;
        }
        await rpc("/access_management/switch_back", {});
        window.location.href = "/odoo";
    }
}

export const systrayItem = {
    Component: SwitchUserMenu,
    isDisplayed: () => Boolean(getAccessManagement().can_switch_user),
};

registry.category("systray").add("access_management_ai.SwitchUserMenu", systrayItem, {
    sequence: 15,
});
