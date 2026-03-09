import { getRequestConfig } from "next-intl/server";

export default getRequestConfig(async ({ requestLocale }) => {
    const locale = await requestLocale;
    return {
        locale: locale ?? "pt",
        messages: (await import(`../messages/${locale ?? "pt"}.json`)).default,
    };
});
