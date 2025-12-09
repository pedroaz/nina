import { LandingPrimaryImageCtaSection } from '@/components/landing/cta/LandingPrimaryCta';

export const metadata = {
    title: 'Terms of Service',
    description: 'Read our Terms of Service governing your use of Nina.',
};

export default function TermsOfService() {
    return (
        <>
            <LandingPrimaryImageCtaSection
                title="Terms of Service"
                description="Please read these Terms of Service carefully before using Nina."
                imageSrc="/nina-teacher.png"
                imageAlt="Terms of Service"
                imagePerspective="left"
            />

            <section className="w-full py-12 lg:py-16 px-6">
                <div className="container mx-auto max-w-4xl prose prose-lg dark:prose-invert max-w-none">
                    <h2>1. Agreement to Terms</h2>
                    <p>
                        By accessing and using Nina, an open-source language learning application ("Service"), you accept and agree to be bound by
                        the terms and provisions of this agreement. If you do not agree to abide by these terms, please do not use this Service.
                    </p>

                    <h2>2. Eligibility</h2>
                    <p>
                        Nina is designed for language learners of all ages. If you are under the age of digital consent in your jurisdiction
                        (typically 16 in the EU), parental or guardian consent is required to use the Service. By using Nina, you confirm that you
                        have such authority or consent.
                    </p>

                    <h2>3. Use License</h2>
                    <p>
                        We grant you a limited, non-exclusive, non-transferable license to use Nina for personal, educational purposes only.
                        This is a license, not a transfer of title. Under this license, you may not:
                    </p>
                    <ul>
                        <li>Modify, copy, or create derivative works of the Service or its content</li>
                        <li>Use the Service for any commercial purpose or for public display (except as explicitly permitted)</li>
                        <li>Attempt to decompile, reverse engineer, or discover the source code (except where open-source licenses apply)</li>
                        <li>Remove any copyright, trademark, or proprietary notices</li>
                        <li>Transfer or "mirror" the Service or its content to another server without authorization</li>
                        <li>Use automated tools (bots, scrapers) to access the Service</li>
                    </ul>

                    <h2>4. Open Source Components</h2>
                    <p>
                        Nina is built on open-source technologies and includes open-source components. The licensing terms of these components
                        are governed by their respective open-source licenses (MIT, Apache 2.0, etc.). Where open-source licenses apply, those
                        licenses take precedence for the specific components they cover.
                    </p>

                    <h2>5. User Accounts and Responsibilities</h2>
                    <p>
                        When you create an account, you agree to:
                    </p>
                    <ul>
                        <li>Provide accurate, complete, and current information</li>
                        <li>Maintain the confidentiality of your password and account credentials</li>
                        <li>Accept responsibility for all activities under your account</li>
                        <li>Notify us immediately of unauthorized access or use</li>
                        <li>Use the Service in compliance with all applicable laws</li>
                    </ul>
                    <p>
                        We reserve the right to suspend or terminate accounts that violate these terms.
                    </p>

                    <h2>6. Prohibited Conduct</h2>
                    <p>You agree not to:</p>
                    <ul>
                        <li>Harass, threaten, or abuse other users</li>
                        <li>Use offensive, obscene, or hate speech</li>
                        <li>Disrupt the normal functioning of the Service</li>
                        <li>Attempt to gain unauthorized access to our systems or other users' accounts</li>
                        <li>Upload or transmit viruses, malware, or harmful code</li>
                        <li>Violate any applicable laws, regulations, or third-party rights</li>
                        <li>Engage in spam, phishing, or fraudulent activities</li>
                        <li>Violate intellectual property rights</li>
                    </ul>

                    <h2>7. Intellectual Property Rights</h2>
                    <p>
                        The Service and its original content, features, and functionality (excluding open-source components) are owned by Nina
                        and protected by international copyright and intellectual property laws. You may not reproduce, distribute, transmit,
                        or display these materials without express written permission, except as permitted by open-source licenses.
                    </p>
                    <p>
                        Any content you create within the Service (learning notes, exercises) remains your property, but you grant us a license
                        to use it to provide and improve the Service.
                    </p>

                    <h2>8. Voluntary Donations and Payments</h2>
                    <p>
                        Nina accepts voluntary donations and payments through Ko-fi to support continued development. Important points:
                    </p>
                    <ul>
                        <li>All donations are voluntary and provide no mandatory service benefits</li>
                        <li>Ko-fi handles all payment processing according to Ko-fi's terms and privacy policy</li>
                        <li>We do not store payment information; Ko-fi manages all financial data</li>
                        <li>Donations are non-refundable unless otherwise specified at the time of donation</li>
                        <li>We make no guarantee that donations will result in specific features or services</li>
                        <li>You are responsible for any taxes associated with donations</li>
                    </ul>

                    <h2>9. Warranty Disclaimers</h2>
                    <p>
                        Nina is provided "AS IS" without warranties of any kind. We disclaim all representations and warranties, express or implied,
                        including merchantability, fitness for a particular purpose, and non-infringement. We do not warrant that:
                    </p>
                    <ul>
                        <li>The Service will be error-free or uninterrupted</li>
                        <li>The Service will meet your specific learning goals</li>
                        <li>Defects in the Service will be corrected</li>
                        <li>The Service is free from viruses or harmful components</li>
                    </ul>

                    <h2>10. Limitation of Liability</h2>
                    <p>
                        To the maximum extent permitted by law, Nina and its creators shall not be liable for:
                    </p>
                    <ul>
                        <li>Indirect, incidental, consequential, or punitive damages</li>
                        <li>Loss of data, profits, revenue, or business interruption</li>
                        <li>Loss or damage arising from your use of or inability to use the Service</li>
                        <li>Any third-party actions, content, or services</li>
                    </ul>
                    <p>
                        This limitation applies even if we have been advised of the possibility of such damages.
                    </p>

                    <h2>11. Indemnification</h2>
                    <p>
                        You agree to indemnify, defend, and hold harmless Nina, its creators, contributors, and representatives from any claims,
                        damages, losses, or expenses (including attorneys' fees) arising from:
                    </p>
                    <ul>
                        <li>Your use of the Service</li>
                        <li>Your violation of these terms</li>
                        <li>Your violation of applicable laws or third-party rights</li>
                        <li>Your content or conduct</li>
                    </ul>

                    <h2>12. Termination</h2>
                    <p>
                        We reserve the right to terminate or suspend your account and access to the Service immediately, without notice, for:
                    </p>
                    <ul>
                        <li>Violation of these terms</li>
                        <li>Violation of applicable law</li>
                        <li>Abuse or misuse of the Service</li>
                        <li>Any reason, with or without cause</li>
                    </ul>
                    <p>
                        Upon termination, your right to use the Service immediately ceases. You remain liable for any obligations incurred.
                    </p>

                    <h2>13. Availability and Service Changes</h2>
                    <p>
                        Nina is provided on an "as available" basis. We make no guarantee of continuous availability. We may:
                    </p>
                    <ul>
                        <li>Modify or discontinue features or the entire Service</li>
                        <li>Perform maintenance that temporarily disrupts access</li>
                        <li>Change the Service's functionality or appearance</li>
                        <li>Migrate to new hosting or infrastructure</li>
                    </ul>
                    <p>
                        We will attempt to provide reasonable notice of major changes, but make no commitment to do so.
                    </p>

                    <h2>14. Governing Law and Jurisdiction</h2>
                    <p>
                        These Terms of Service are governed by the laws of the European Union and, specifically, the laws of Germany,
                        without regard to conflict of law principles. Any disputes shall be resolved in accordance with German law and
                        the laws of the EU, with exclusive jurisdiction in German courts.
                    </p>

                    <h2>15. Entire Agreement</h2>
                    <p>
                        These Terms of Service, together with our Privacy Policy, constitute the entire agreement between you and Nina regarding
                        your use of the Service. These terms supersede all prior negotiations, representations, and agreements.
                    </p>

                    <h2>16. Severability</h2>
                    <p>
                        If any provision of these terms is found to be invalid or unenforceable, that provision shall be modified to the minimum
                        extent necessary to make it enforceable, or if not possible, severed. The remaining provisions shall remain in full effect.
                    </p>

                    <h2>17. Changes to Terms</h2>
                    <p>
                        We may update these Terms of Service at any time. We will notify you of material changes by posting the updated terms on
                        our website with an updated "Last Updated" date. Your continued use of the Service after such notification constitutes your
                        acceptance of the updated terms. If you do not agree with the changes, you must stop using the Service.
                    </p>

                    <h2>18. Contact Information</h2>
                    <p>
                        For questions about these Terms of Service, please contact us at:
                        <br />
                        Email: legal@nina-learn.de
                    </p>

                    <h2>19. Safety and Appropriate Use</h2>
                    <p>
                        For young learners and their guardians: Nina is designed to be a safe learning environment. We encourage:
                    </p>
                    <ul>
                        <li>Parents/guardians to review the service and monitor their child's use</li>
                        <li>Reporting of any inappropriate content or behavior to legal@nina-learn.de</li>
                        <li>Open communication about online safety and privacy</li>
                    </ul>

                    <p className="text-sm opacity-70 mt-8">
                        Last Updated: December 2025
                    </p>
                </div>
            </section>
        </>
    );
}
