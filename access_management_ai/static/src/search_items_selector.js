/** Copyright (C) NexGen Solutions */
/** @odoo-module **/
import { Component, proxy, t, useProps, useOnChange, onWillDestroy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { relationId } from "./dynamic_element_selection";

export class AmSearchItemsSelector extends Component {
    static template = "access_management_ai.AmSearchItemsSelector";
    props = useProps({ ...standardFieldProps, itemType: t.string().optional("filter") });

    setup() {
        this.orm = useService("orm");
        this.state = proxy({ availableItems: [], loading: false });
        this.loadSequence = 0;
        onWillDestroy(() => this.loadSequence++);
        useOnChange(
            () => [relationId(this.props.record.data.model_id), this.props.itemType],
            (modelId, itemType) => this.loadItems(modelId, itemType)
        );
    }

    get selectedKeys() {
        const value = this.props.record.data[this.props.name];
        return value ? value.split(",").map((key) => key.trim()).filter(Boolean) : [];
    }

    async loadItems(modelId, itemType) {
        const sequence = ++this.loadSequence;
        this.state.availableItems = [];
        this.state.loading = Boolean(modelId);
        if (!modelId) return;
        try {
            const items = await this.orm.call(
                "access.management.model", "get_search_menu_items", [modelId, itemType]
            );
            if (sequence === this.loadSequence) this.state.availableItems = items || [];
        } finally {
            if (sequence === this.loadSequence) this.state.loading = false;
        }
    }

    toggleKey(key) {
        if (this.props.readonly) return;
        const current = new Set(this.selectedKeys);
        if (current.has(key)) current.delete(key);
        else current.add(key);
        return this.props.record.update({ [this.props.name]: [...current].join(",") || false });
    }
}

registry.category("fields").add("am_search_items_selector", {
    component: AmSearchItemsSelector,
    supportedTypes: ["char"],
    extractProps: ({ options }) => ({ itemType: options.item_type || "filter" }),
});
