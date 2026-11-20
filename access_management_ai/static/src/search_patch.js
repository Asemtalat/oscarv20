/** Copyright (C) NexGen Solutions */
/** @odoo-module **/
import { onMounted, onPatched } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { SearchBarMenu } from "@web/search/search_bar_menu/search_bar_menu";

import { SearchModel } from "@web/search/search_model";

import { getModelRestrictions } from "./access_management";

function restrictionsFor(component) {
    const model = component.env.searchModel && component.env.searchModel.resModel;
    return model ? getModelRestrictions(model) : {};
}

function isHiddenSearchItem(item, hiddenKeys) {
    if (!hiddenKeys || !hiddenKeys.length) {
        return false;
    }
    const hidden = new Set(hiddenKeys);
    return (
        (item.name && hidden.has(item.name)) ||
        (item.description && hidden.has(item.description)) ||
        (item.fieldName && hidden.has(item.fieldName))
    );
}

patch(SearchModel.prototype, {
    async load(config) {
        await super.load(...arguments);
        const restrictions = getModelRestrictions(this.resModel);
        if (restrictions.hide_filters && this.searchMenuTypes) {
            this.searchMenuTypes.delete("filter");
        }
        if (restrictions.hide_groupby && this.searchMenuTypes) {
            this.searchMenuTypes.delete("groupBy");
        }
        if (restrictions.hide_favorites && this.searchMenuTypes) {
            this.searchMenuTypes.delete("favorite");
        }
        if (restrictions.hide_custom_group) {
            this.hideCustomGroupBy = true;
        }
        this._amDropHiddenSearchQuery(restrictions);
    },

    _amDropHiddenSearchQuery(restrictions) {
        const hiddenFilters = restrictions.hidden_filters || [];
        const hiddenGroupbys = restrictions.hidden_groupbys || [];
        if ((!hiddenFilters.length && !hiddenGroupbys.length) || !this.query) {
            return;
        }
        const before = this.query.length;
        this.query = this.query.filter((queryElem) => {
            const item = this.searchItems[queryElem.searchItemId];
            if (!item) {
                return true;
            }
            if (["filter", "dateFilter"].includes(item.type)) {
                return !isHiddenSearchItem(item, hiddenFilters);
            }
            if (["groupBy", "dateGroupBy"].includes(item.type)) {
                return !isHiddenSearchItem(item, hiddenGroupbys);
            }
            return true;
        });
        if (this.query.length !== before) {
            this._reset();
        }
    },

    async spawnCustomFilterDialog() {
        if (getModelRestrictions(this.resModel).hide_custom_filter) {
            return;
        }
        return super.spawnCustomFilterDialog(...arguments);
    },

    _getDisplay(display = {}) {
        const result = super._getDisplay(display);
        const restrictions = getModelRestrictions(this.resModel);

        if (restrictions.hide_search_panel) {
            result.searchPanel = false;
        }
        return result;
    }
});

// Hide Filters / Group By / Favorites sections in the search dropdown (fallback/extra safety).
patch(SearchBarMenu.prototype, {
    get filterItems() {
        const restrictions = restrictionsFor(this);
        if (restrictions.hide_filters) {
            return [];
        }
        const items = super.filterItems;
        return items.filter((item) => !isHiddenSearchItem(item, restrictions.hidden_filters));
    },
    get groupByItems() {
        const restrictions = restrictionsFor(this);
        if (restrictions.hide_groupby) {
            return [];
        }
        const items = super.groupByItems;
        return items.filter((item) => !isHiddenSearchItem(item, restrictions.hidden_groupbys));
    },
    get favorites() {
        return restrictionsFor(this).hide_favorites ? [] : super.favorites;
    },
    get sharedFavorites() {
        return restrictionsFor(this).hide_favorites ? [] : super.sharedFavorites;
    },
    get hideCustomGroupBy() {
        return super.hideCustomGroupBy || Boolean(restrictionsFor(this).hide_custom_group);
    },
    get hideCustomFilter() {
        return Boolean(restrictionsFor(this).hide_custom_filter);
    },
    async onAddCustomFilterClick() {
        if (this.hideCustomFilter) {
            return;
        }
        return super.onAddCustomFilterClick(...arguments);
    },
});

// Hide the search bar input entirely / omit Custom Filter autocomplete entry.
patch(SearchBar.prototype, {
    setup() {
        super.setup(...arguments);
        const apply = () => {
            const el = this.root();
            if (el) {
                el.classList.toggle("o-am-hidden", Boolean(restrictionsFor(this).hide_searchbar));
            }
        };
        onMounted(apply);
        onPatched(apply);
    },
    async computeState(options = {}) {
        await super.computeState(...arguments);
        if (restrictionsFor(this).hide_custom_filter) {
            this.items = this.items.filter((item) => !item.isAddCustomFilterButton);
        }
    },
});

