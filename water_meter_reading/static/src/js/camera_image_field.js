/** @odoo-module **/
import { registry } from "@web/core/registry";
import { ImageField, imageField } from "@web/views/fields/image/image_field";
import { onMounted, onPatched } from "@odoo/owl";

/**
 * CameraImageField: extends ImageField to force direct camera capture on mobile.
 * Adds capture="environment" to the hidden file input after each render so that
 * on Android/iOS tapping the button opens the rear camera directly.
 */
class CameraImageField extends ImageField {
    setup() {
        super.setup();
        const enableCapture = () => {
            if (!this.el) return;
            this.el.querySelectorAll('input[type="file"]').forEach((input) => {
                input.setAttribute("capture", "environment");
                if (!input.accept) {
                    input.setAttribute("accept", "image/*");
                }
            });
        };
        onMounted(enableCapture);
        onPatched(enableCapture);
    }
}

registry.category("fields").add("camera_image", {
    ...imageField,
    component: CameraImageField,
});
