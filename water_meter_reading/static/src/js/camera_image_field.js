/** @odoo-module **/

import { getDataURLFromFile } from "@web/core/utils/urls";
import { checkFileSize } from "@web/core/utils/files";
import { registry } from "@web/core/registry";
import { ImageField, imageField } from "@web/views/fields/image/image_field";

import { useRef } from "@odoo/owl";


class CameraImageField extends ImageField {
    static template = "water_meter_reading.CameraImageField";

    setup() {
        super.setup();
        this.cameraInput = useRef("cameraInput");
    }

    onCameraClick() {
        this.cameraInput.el.click();
    }

    async onCameraFileChange(event) {
        const [file] = event.target.files;
        if (!file || !checkFileSize(file.size, this.notification)) {
            return;
        }
        const data = await getDataURLFromFile(file);
        await this.onFileUploaded({
            name: file.name,
            size: file.size,
            type: file.type,
            data: data.split(",")[1],
        });
        event.target.value = null;
    }
}

registry.category("fields").add("camera_image", {
    ...imageField,
    component: CameraImageField,
});