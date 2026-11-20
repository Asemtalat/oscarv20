/** Copyright (C) NexGen Solutions */
/** @odoo-module **/
import { onMounted, onPatched } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { getAccessManagement, getModelRestrictions } from "./access_management";

function spreadsheetRestricted(resModel) {
    return Boolean(
        (getAccessManagement().global || {}).hide_spreadsheet ||
        getModelRestrictions(resModel).hide_spreadsheet
    );
}

if ((getAccessManagement().global || {}).hide_spreadsheet) {
    session.can_insert_in_spreadsheet = false;
}

function hideSpreadsheetButtons(root = document, resModel) {
    if (!spreadsheetRestricted(resModel)) {
        return;
    }
    const selectors = [
        ".o_list_button_add_to_spreadsheet",
        "button[name='action_insert_in_spreadsheet']",
        "button[data-menu-xmlid='spreadsheet.menu_insert_in_spreadsheet']",
    ];
    root.querySelectorAll(selectors.join(",")).forEach((node) => {
        node.classList.add("o-am-hidden");
    });
    root.querySelectorAll("button, a, [role='menuitem']").forEach((node) => {
        const label = `${node.getAttribute("aria-label") || ""} ${node.getAttribute("title") || ""} ${node.textContent || ""}`;
        if (/insert\s+in\s+spreadsheet/i.test(label)) {
            node.classList.add("o-am-hidden");
        }
    });
}

function getResModel(ctx) {
    if (!ctx) return null;
    if (ctx.props && ctx.props.resModel) return ctx.props.resModel;
    if (ctx.env && ctx.env.searchModel && ctx.env.searchModel.resModel) return ctx.env.searchModel.resModel;
    if (ctx.searchModel && ctx.searchModel.resModel) return ctx.searchModel.resModel;
    if (ctx.model && ctx.model.root && ctx.model.root.resModel) return ctx.model.root.resModel;
    if (ctx.config && ctx.config.action && ctx.config.action.res_model) return ctx.config.action.res_model;
    if (ctx.config && ctx.config.resModel) return ctx.config.resModel;
    return null;
}

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        const originalGetStaticActionMenuItems = this.getStaticActionMenuItems;
        if (originalGetStaticActionMenuItems) {
            this.getStaticActionMenuItems = function() {
                const menuItems = originalGetStaticActionMenuItems.apply(this, arguments) || {};
                const resModel = getResModel(this);
                if (resModel && spreadsheetRestricted(resModel)) {
                    delete menuItems["insert"];
                }
                return menuItems;
            };
        }

        const apply = () => hideSpreadsheetButtons(this.el || document, getResModel(this));
        onMounted(apply);
        onPatched(apply);
    },
});

if (KanbanController) {
    patch(KanbanController.prototype, {
        setup() {
            super.setup(...arguments);
            const originalGetStaticActionMenuItems = this.getStaticActionMenuItems;
            if (originalGetStaticActionMenuItems) {
                this.getStaticActionMenuItems = function() {
                    const menuItems = originalGetStaticActionMenuItems.apply(this, arguments) || {};
                    const resModel = getResModel(this);
                    if (resModel && spreadsheetRestricted(resModel)) {
                        delete menuItems["insert"];
                    }
                    return menuItems;
                };
            }
        },
    });
}


// Patch the spreadsheet cog menu for pivot and graph views in modern Odoo
const cogMenuRegistry = registry.category("cogMenu");
// Because the item might be added after this file is parsed (depending on module load order),
// we patch the registry's add method or wait for it.
// Actually, cogMenu is usually fully registered if spreadsheet_edition is loaded.
// To be safe, we can patch the `add` method of cogMenuRegistry.
const originalAdd = cogMenuRegistry.add;
cogMenuRegistry.add = function (key, item, options) {
    if (key === "spreadsheet-cog-menu" && item.isDisplayed) {
        const originalIsDisplayed = item.isDisplayed;
        item.isDisplayed = (env) => {
            const resModel = getResModel(env);
            if (resModel && spreadsheetRestricted(resModel)) {
                return false;
            }
            return originalIsDisplayed(env);
        };
    }
    return originalAdd.call(this, key, item, options);
};

// Also patch if it's already added
const spreadsheetCogMenu = cogMenuRegistry.get("spreadsheet-cog-menu", null);
if (spreadsheetCogMenu && spreadsheetCogMenu.isDisplayed) {
    const originalIsDisplayed = spreadsheetCogMenu.isDisplayed;
    spreadsheetCogMenu.isDisplayed = (env) => {
        const resModel = getResModel(env);
        if (resModel && spreadsheetRestricted(resModel)) {
            return false;
        }

        return originalIsDisplayed(env);
    };
}
