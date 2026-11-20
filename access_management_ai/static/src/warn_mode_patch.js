/** Copyright (C) NexGen Solutions */
/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";
import { getModelRestrictions } from "./access_management";

/**
 * Soft restriction / warn-mode support.
 *
 * When `warn_mode` is enabled for a model, instead of hard-blocking CRUD
 * actions the user gets a warning notification before proceeding.
 */
function _getWarnMessage(resModel) {
    const cfg = getModelRestrictions(resModel);
    if (!cfg.warn_mode) {
        return null;
    }
    return cfg.warn_message || "This action is restricted. Please proceed with caution.";
}

// Patch FormController to show a warning when saving a record on a warn-mode model.
patch(FormController.prototype, {
    async onRecordSaved(record) {
        const msg = _getWarnMessage(this.props.resModel);
        if (msg) {
            this.env.services.notification.add(msg, {
                title: "Access Warning",
                type: "warning",
                sticky: false,
            });
        }
        return super.onRecordSaved(...arguments);
    },
    async beforeExecuteActionButton(clickParams) {
        const msg = _getWarnMessage(this.props.resModel);
        if (msg && clickParams.type === "object") {
            this.env.services.notification.add(msg, {
                title: "Access Warning",
                type: "warning",
                sticky: false,
            });
        }
        return super.beforeExecuteActionButton(...arguments);
    },
});

// Patch ListController to show warning on record deletion attempts.
patch(ListController.prototype, {
    async onDeleteSelectedRecords() {
        const msg = _getWarnMessage(this.props.resModel);
        if (msg) {
            this.env.services.notification.add(msg, {
                title: "Access Warning",
                type: "warning",
                sticky: false,
            });
        }
        return super.onDeleteSelectedRecords(...arguments);
    },
});
