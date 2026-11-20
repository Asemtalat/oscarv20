/** Copyright (C) NexGen Solutions */
/** @odoo-module **/
import { Component, proxy, useProps, useOnChange, onWillDestroy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

export function relationId(value) {
    if (!value) return false;
    if (Array.isArray(value)) return value[0];
    return typeof value === "object" ? value.id ?? value.resId ?? false : value;
}

export class DynamicElementSelection extends Component {
    static template = "access_management_ai.DynamicElementSelection";
    props = useProps(standardFieldProps);

    setup() {
        this.orm = useService("orm");
        this.state = proxy({ choices: [] });
        this.loadSequence = 0;
        onWillDestroy(() => this.loadSequence++);
        useOnChange(
            () => [
                relationId(this.props.record.data.model_id),
                this.props.record.data.view_type || "form",
                this.props.record.data.element_type || "button",
            ],
            (modelId, viewType, elementType) => this.loadChoices(modelId, viewType, elementType)
        );
    }

    async loadChoices(modelId, viewType, elementType) {
        const sequence = ++this.loadSequence;
        this.state.choices = [];
        if (!modelId) return;
        const choices = await this.orm.call(
            "access.management.element", "get_ui_elements", [modelId, viewType, elementType]
        );
        if (sequence === this.loadSequence) this.state.choices = choices;
    }

    onChange(ev) {
        if (!this.props.readonly) {
            return this.props.record.update({ [this.props.name]: ev.target.value || false });
        }
    }
}

registry.category("fields").add("dynamic_element_selection", {
    component: DynamicElementSelection,
    displayName: "Dynamic Element Selection",
    supportedTypes: ["char"],
});
