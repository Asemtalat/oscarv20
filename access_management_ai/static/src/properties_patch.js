/** Copyright (C) NexGen Solutions */
/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { PropertiesField } from "@web/views/fields/properties/properties_field";
import { getModelRestrictions } from "./access_management";

/** Disable definition editing (incl. the "Add Property" button) when restricted. */
patch(PropertiesField.prototype, {
    async checkDefinitionWriteAccess() {
        const model = this.props.record && this.props.record.resModel;
        if (model && getModelRestrictions(model).hide_add_property) {
            return false;
        }
        return super.checkDefinitionWriteAccess(...arguments);
    },
});
