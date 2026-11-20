/** Copyright (C) NexGen Solutions */
/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { getModelRestrictions } from "./access_management";

/** Disable the Archive/Unarchive actions for models restricted for this user. */
// FormController uses a getter in Odoo 20.
patch(FormController.prototype, {
    get archiveEnabled() {
        if (getModelRestrictions(this.props.resModel).hide_archive) {
            return false;
        }
        return super.archiveEnabled;
    }
});

// ListController uses a normal property set in setup() in Odoo 20.
patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        if (getModelRestrictions(this.props.resModel).hide_archive) {
            this.archiveEnabled = false;
        }
    }
});

patch(KanbanController.prototype, {
    setup() {
        super.setup(...arguments);
        if (getModelRestrictions(this.props.resModel).hide_archive) {
            this.archiveEnabled = false;
        }
    },
});
