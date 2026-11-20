/** Copyright (C) NexGen Solutions */
/** @odoo-module **/
import { session } from "@web/session";

/**
 * Per-user access management configuration delivered in the session info by
 * `ir.http.session_info` (see models/ir_http.py).
 */
export function getAccessManagement() {
    return session.access_management_ai || {};
}

export function getModelRestrictions(resModel) {
    const models = getAccessManagement().models || {};
    const global = getAccessManagement().global || {};
    const model = models[resModel] || {};
    
    // Fallback: apply hr.employee rules to hr.employee.public if not specifically defined
    let fallbackModel = {};
    if (resModel === 'hr.employee.public') {
        fallbackModel = models['hr.employee'] || {};
    }
    
    const result = {};
    const allKeys = new Set([...Object.keys(global), ...Object.keys(model), ...Object.keys(fallbackModel)]);

    for (const key of allKeys) {
        if (key === 'chatter') continue;
        if (key === 'warn_message') {
            result[key] = model[key] || fallbackModel[key] || global[key] || '';
            continue;
        }
        if (key === 'hidden_filters' || key === 'hidden_groupbys') {
            const merged = [
                ...(global[key] || []),
                ...(model[key] || []),
                ...(fallbackModel[key] || []),
            ];
            result[key] = [...new Set(merged)];
            continue;
        }
        result[key] = Boolean(global[key]) || Boolean(model[key]) || Boolean(fallbackModel[key]);
    }
    
    // Merge chatter separately (though typically handled by getChatterForModel)
    const globalChatter = global.chatter || {};
    const modelChatter = model.chatter || fallbackModel.chatter || {};
    result.chatter = {};
    const chatterKeys = new Set([...Object.keys(globalChatter), ...Object.keys(modelChatter)]);
    for (const key of chatterKeys) {
        result.chatter[key] = Boolean(globalChatter[key]) || Boolean(modelChatter[key]);
    }
    
    return result;
}

/** Merge profile-global chatter flags with the per-model ones (logical OR). */
export function getChatterForModel(resModel) {
    const g = getAccessManagement().chatter_global || {};
    const m = (getModelRestrictions(resModel) || {}).chatter || {};
    const keys = ["hide", "send_message", "log_note", "activities", "followers", "attachments", "search"];
    const result = {};
    for (const k of keys) {
        result[k] = Boolean(g[k]) || Boolean(m[k]);
    }
    return result;
}

export function getHiddenSystrayKeys() {
    return new Set(getAccessManagement().systray || []);
}

export function isDevModeRestricted() {
    return Boolean(getAccessManagement().disable_dev_mode);
}
