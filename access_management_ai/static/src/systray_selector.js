/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, proxy, useProps, onWillStart } from "@odoo/owl";

export class AmSystraySelector extends Component {
    static template = "access_management_ai.AmSystraySelector";
    props = useProps(standardFieldProps);

    setup() {
        this.state = proxy({
            availableItems: [],
        });

        onWillStart(async () => {
            this._loadAvailableItems();
        });
    }

    get selectedKeys() {
        const val = this.props.record.data[this.props.name];
        return val ? val.split(",").map(k => k.trim()).filter(k => k) : [];
    }

    _loadAvailableItems() {
        const systrayRegistry = registry.category("systray");
        const items = systrayRegistry.getEntries();
        const seen = new Set();
        this.state.availableItems = [];

        const pushItem = (key, label, help) => {
            if (seen.has(key)) {
                return;
            }
            seen.add(key);
            this.state.availableItems.push({
                key,
                label: label || this._formatLabel(key),
                help: help || this._getHelpText(key, label || this._formatLabel(key)),
            });
        };

        // Always offer Switch User so it can be hidden from Access Rules
        // even if the systray asset has not registered yet in this session.
        pushItem(
            "access_management_ai.SwitchUserMenu",
            "Switch User",
            "Hide the Switch User icon from the navbar (Access Administrators)."
        );

        for (const [key] of items) {
            const label = this._formatLabel(key);
            pushItem(key, label, this._getHelpText(key, label));
        }

        // User-menu entries (not systray registry keys)
        pushItem("account", "My Odoo.com Account", "Hide the 'My Odoo.com Account' option from the User Profile menu.");
        pushItem("support", "Help", "Hide the 'Help' option from the User Profile menu.");
        pushItem("shortcuts", "Shortcuts", "Hide the 'Shortcuts' option from the User Profile menu.");
    }

    _getHelpText(key, label) {
        const descriptions = {
            "access_management_ai.SwitchUserMenu": "Hide the Switch User icon from the navbar (Access Administrators).",
            "mail.messaging_menu": "Hide the Messaging / Chat icon.",
            "mail.activity_menu": "Hide the Activities (clock) icon.",
            "SwitchCompanyMenu": "Hide the Multi-Company switcher.",
            "web.debug_mode_menu": "Hide the Developer Mode (bug) icon.",
            "web.user_menu": "Hide the User Profile menu.",
            "burger_menu": "Hide the Mobile Burger menu (mobile views).",
            "web_cloud.tour_pointer": "Hide the Odoo Tour/Onboarding pointers.",
            "ThemeStudioMenu": "Hide the Theme Studio menu.",
            "account": "Hide the 'My Odoo.com Account' option from the User Profile menu.",
            "support": "Hide the 'Help' option from the User Profile menu.",
            "shortcuts": "Hide the 'Shortcuts' option from the User Profile menu.",
            "discuss.CallMenu": "Hide the Call Menu (Discuss app).",
            "voip": "Hide the VoIP Phone icon (Call Menu).",
        };
        return descriptions[key] || `Hide the ${label} from the top navigation bar.`;
    }

    _formatLabel(key) {
        if (key === "access_management_ai.SwitchUserMenu") {
            return "Switch User";
        }
        // e.g., "mail.messaging_menu" -> "Messaging Menu"
        const parts = key.split(".");
        let name = parts[parts.length - 1];
        name = name.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/_/g, " ");
        return name.replace(/\b\w/g, (l) => l.toUpperCase());
    }

    toggleKey(key) {
        if (this.props.readonly) {
            return;
        }
        let current = [...this.selectedKeys];
        if (current.includes(key)) {
            current = current.filter(k => k !== key);
        } else {
            current.push(key);
        }

        const newVal = current.length ? current.join(",") : false;
        this.props.record.update({ [this.props.name]: newVal });
    }
}

registry.category("fields").add("am_systray_selector", {
    component: AmSystraySelector,
});
