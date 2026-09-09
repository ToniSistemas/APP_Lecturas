/** @odoo-module **/
import { registry } from "@web/core/registry";
import { ImageField, imageField } from "@web/views/fields/image/image_field";
import { onMounted, onPatched } from "@odoo/owl";

/** Allow mobile browsers to offer both camera capture and the image gallery. */
class CameraImageField extends ImageField {
    setup() {
        super.setup();
        const enableMobileImageSources = () => {
            if (!this.el) return;
            this.el.querySelectorAll('input[type="file"]').forEach((input) => {
                input.setAttribute("accept", "image/*");
                input.removeAttribute("capture");
            });
        };
        onMounted(enableMobileImageSources);
        onPatched(enableMobileImageSources);
    }
}

registry.category("fields").add("camera_image", {
    ...imageField,
    component: CameraImageField,
});
