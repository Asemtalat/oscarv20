/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { getModelRestrictions } from "./access_management";

function hideExportAction(controller, items) {
    const restrictions = getModelRestrictions(controller.props.resModel);
    if (restrictions.hide_export && items.export) {
        items.export.isAvailable = () => false;
    }
    return items;
}

patch(ListController.prototype, {
    getStaticActionMenuItems() {
        return hideExportAction(this, super.getStaticActionMenuItems(...arguments));
    },
});

patch(KanbanController.prototype, {
    getStaticActionMenuItems() {
        return hideExportAction(this, super.getStaticActionMenuItems(...arguments));
    },
});
