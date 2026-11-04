/** @odoo-module **/
/* global window, setTimeout */

import {App, useRef, whenReady} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {AlertDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {makeEnv, startServices} from "@web/env";
import SignOcaPdf from "../sign_oca_pdf/sign_oca_pdf.esm.js";
import {getTemplate} from "@web/core/templates";
import {MainComponentsContainer} from "@web/core/main_components_container";
import {rpc} from "@web/core/network/rpc";
import {startSignItemNavigator} from "./sign_oca_navigator.esm";

// The pdf.js iframe may need a moment before the fields are rendered, so the
// button retries a limited number of times before warning the signer.
const SIGN_FIELD_RETRY_DELAY = 500;
const SIGN_FIELD_MAX_RETRIES = 30;

export class SignOcaPdfPortal extends SignOcaPdf {
    setup() {
        this.rpc = rpc;
        this.signOcaFooter = useRef("sign_oca_footer");
        this.signer_id = this.props.signer_id;
        this.access_token = this.props.access_token;
        this.signFieldRetries = 0;
        super.setup(...arguments);
    }
    async willStart() {
        this.info = await this.rpc(
            "/sign_oca/info/" + this.signer_id + "/" + this.access_token
        );
    }
    getPdfUrl() {
        return "/sign_oca/content/" + this.signer_id + "/" + this.access_token;
    }
    checkToSign() {
        this.to_sign = this.to_sign_update;
        if (this.to_sign_update) {
            $(this.signOcaFooter.el).show();
            $("#sign_oca_button").removeAttr("disabled");
        } else {
            $(this.signOcaFooter.el).hide();
            $("#sign_oca_button").prop("disabled", true);
        }
    }
    postIframeFields() {
        super.postIframeFields(...arguments);
        this.checkFilledAll();
        // Is essential to make sure the navigator will never duplicate
        const target = $(
            this.iframe.el.contentDocument.getElementById("viewerContainer")
        );
        const navigator = $(
            this.iframe.el.contentDocument.getElementsByClassName(
                "o_sign_sign_item_navigator"
            )
        );
        const navLine = $(
            this.iframe.el.contentDocument.getElementsByClassName(
                "o_sign_sign_item_navline"
            )
        );
        if (navLine.length === 0) {
            target.append($("<div class='o_sign_sign_item_navline'/>"));
        }
        if (navigator.length === 0) {
            target.append($("<div class='o_sign_sign_item_navigator'/>"));
        }
        // Load navigator
        this.navigate();
    }
    async _onClickSign(ev) {
        ev.target.disabled = true;
        const position = await this.getLocation();
        this.rpc("/sign_oca/sign/" + this.signer_id + "/" + this.access_token, {
            items: this.info.items,
            latitude: position && position.coords && position.coords.latitude,
            longitude: position && position.coords && position.coords.longitude,
        }).then((action) => {
            // As we are on frontend env, it is not possible to use do_action(), so we
            // redirect to the corresponding URL or reload the page if the action is not
            // an url.
            if (action.type === "ir.actions.act_url") {
                window.location = action.url;
            } else {
                window.location.reload();
            }
        });
    }
    getSignatureField() {
        const doc = this.iframe && this.iframe.el && this.iframe.el.contentDocument;
        if (!doc) {
            return null;
        }
        const fields = [...doc.querySelectorAll(".o_sign_oca_field")];
        // Prefer the first field that has not been signed yet.
        return fields.find((field) => !field.querySelector("img")) || fields[0] || null;
    }
    openSignatureField() {
        const field = this.getSignatureField();
        if (field) {
            this.signFieldRetries = 0;
            field.scrollIntoView({behavior: "smooth", block: "center"});
            const clickable = field.firstElementChild || field;
            clickable.click();
            return;
        }
        if (this.signFieldRetries >= SIGN_FIELD_MAX_RETRIES) {
            this.dialogService.add(AlertDialog, {
                body: _t(
                    "The document is not ready yet. Please reload the page and try again."
                ),
            });
            return;
        }
        if (this.signFieldRetries === 0) {
            // The iframe may not have rendered the fields yet.
            this.postIframeFields();
        }
        this.signFieldRetries += 1;
        setTimeout(() => this.openSignatureField(), SIGN_FIELD_RETRY_DELAY);
    }
    navigate() {
        const target = this.iframe.el.contentDocument.getElementById("viewerContainer");
        this.navigator = startSignItemNavigator(this, target, this.env);
    }
}
SignOcaPdfPortal.template = "sign_oca.SignOcaPdfPortal";
SignOcaPdfPortal.props = {
    access_token: String,
    signer_id: Number,
};
SignOcaPdfPortal.components = {MainComponentsContainer};

export async function initDocumentToSign(document, sign_oca_backend_info) {
    const env = makeEnv();
    await startServices(env);
    await whenReady();
    const app = new App(SignOcaPdfPortal, {
        getTemplate,
        env: env,
        dev: env.debug,
        props: {
            access_token: sign_oca_backend_info.access_token,
            signer_id: sign_oca_backend_info.signer_id,
        },
        translateFn: _t,
        translatableAttributes: ["data-tooltip"],
    });
    await app.mount(document.body);
}
export default {SignOcaPdfPortal, initDocumentToSign};
