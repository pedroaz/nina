import { LandingPrimaryImageCtaSection } from '@/components/landing/cta/LandingPrimaryCta';

export const metadata = {
    title: 'Privacy Policy',
    description: 'Learn how Nina protects your data and privacy.',
};

export default function PrivacyPolicy() {
    return (
        <>
            <LandingPrimaryImageCtaSection
                title="Privacy Policy"
                description="Your privacy is important to us. Learn how we collect, use, and protect your personal data."
                imageSrc="/nina-teacher.png"
                imageAlt="Privacy Policy"
                imagePerspective="left"
            />

            <section className="w-full py-12 lg:py-16 px-6">
                <div className="container mx-auto max-w-4xl prose prose-lg dark:prose-invert max-w-none">
                    <h2>1. Introduction</h2>
                    <p>
                        Nina is an open-source language learning application committed to protecting your privacy. This Privacy Policy explains
                        how we collect, use, disclose, and safeguard your information when you use our website and application (collectively, the "Services").
                        We are committed to transparent data practices and full compliance with the General Data Protection Regulation (GDPR) and other
                        applicable EU data protection laws.
                    </p>

                    <h2>2. Data Controller and Contact Information</h2>
                    <p>
                        For questions about this Privacy Policy or how we handle your data, please contact us at:
                        <br />
                        Email: privacy@nina-learn.de
                        <br />
                        <br />
                        We are committed to responding to privacy inquiries within 30 days.
                    </p>

                    <h2>3. Legal Basis for Processing</h2>
                    <p>
                        We process your personal data based on the following legal bases under GDPR:
                    </p>
                    <ul>
                        <li><strong>Contractual necessity</strong>: To provide you with the Services</li>
                        <li><strong>Your consent</strong>: For marketing communications (where applicable)</li>
                        <li><strong>Legitimate interests</strong>: To improve our Services and prevent fraud</li>
                        <li><strong>Legal obligation</strong>: To comply with applicable laws</li>
                    </ul>

                    <h2>4. Information We Collect</h2>
                    <h3>4.1 Information You Provide Directly</h3>
                    <p>We collect information you voluntarily provide, including:</p>
                    <ul>
                        <li>Account registration information (name, email address, password)</li>
                        <li>Profile information (language proficiency level, learning goals, age group)</li>
                        <li>Communication data (messages, feedback, support requests)</li>
                        <li>Payment information processed through Ko-fi (handled by Ko-fi, not stored directly by us)</li>
                    </ul>

                    <h3>4.2 Information Collected Automatically</h3>
                    <p>When you access our Services, we may collect:</p>
                    <ul>
                        <li>Device information (browser type, device type, operating system)</li>
                        <li>Log data (timestamps, pages visited, referral source)</li>
                        <li>Learning analytics (exercises completed, progress tracking, time spent learning)</li>
                        <li>Essential cookies (for authentication and functionality only)</li>
                    </ul>

                    <h2>5. How We Use Your Information</h2>
                    <p>We use your personal data to:</p>
                    <ul>
                        <li>Provide and maintain the Services</li>
                        <li>Personalize your learning experience based on your progress and goals</li>
                        <li>Respond to your inquiries and support requests</li>
                        <li>Send administrative and transactional communications</li>
                        <li>Improve and optimize our Services</li>
                        <li>Comply with legal obligations</li>
                        <li>Prevent fraud and abuse</li>
                    </ul>

                    <h2>6. Data Storage and Location</h2>
                    <p>
                        Your personal data is stored exclusively on servers located within the European Union, ensuring compliance with GDPR and
                        other European data protection regulations. We implement appropriate technical and organizational security measures including
                        encryption, secure authentication, and regular security audits to protect your information from unauthorized access, alteration,
                        disclosure, or destruction.
                    </p>

                    <h2>7. Data Retention</h2>
                    <p>
                        We retain your personal data for as long as necessary to provide the Services and fulfill the purposes outlined in this policy.
                        Specifically:
                    </p>
                    <ul>
                        <li>Account data is retained for the duration of your account unless you request deletion</li>
                        <li>Learning progress data is retained to enable service continuity</li>
                        <li>Transaction records are retained for as long as required by applicable law</li>
                        <li>Upon account deletion, we remove all personal data within 30 days, except where legal retention is required</li>
                    </ul>

                    <h2>8. Data Sharing and Disclosure</h2>
                    <p>
                        We do not sell, trade, or rent your personal data to third parties. We only share information in the following circumstances:
                    </p>
                    <ul>
                        <li><strong>Ko-fi</strong>: For processing voluntary donations/payments (Ko-fi's privacy policy applies)</li>
                        <li><strong>Essential service providers</strong>: Only those necessary to operate our Services, bound by confidentiality agreements</li>
                        <li><strong>Legal compliance</strong>: When required by law or to protect our legal rights</li>
                        <li><strong>Your consent</strong>: Only with your explicit prior consent</li>
                    </ul>

                    <h2>9. Your GDPR Rights</h2>
                    <p>
                        You have the following rights regarding your personal data:
                    </p>
                    <ul>
                        <li><strong>Right to access</strong>: Request a copy of your personal data</li>
                        <li><strong>Right to rectification</strong>: Request correction of inaccurate data</li>
                        <li><strong>Right to erasure</strong>: Request deletion of your data ("Right to be forgotten")</li>
                        <li><strong>Right to restrict processing</strong>: Request limitations on how we use your data</li>
                        <li><strong>Right to data portability</strong>: Receive your data in a portable format</li>
                        <li><strong>Right to object</strong>: Object to certain types of processing</li>
                        <li><strong>Right to withdraw consent</strong>: Withdraw consent at any time without affecting prior processing</li>
                    </ul>
                    <p>
                        To exercise any of these rights, please contact us at privacy@nina-learn.de. We will respond within 30 days.
                    </p>

                    <h2>10. Cookies and Tracking</h2>
                    <p>
                        We use only essential cookies necessary for authentication and functionality. We do not use tracking cookies or analytics cookies
                        that identify you personally. You can control cookie settings through your browser settings, though this may affect some features.
                    </p>

                    <h2>11. Third-Party Services</h2>
                    <p>
                        Our Services may contain links to third-party websites or services (such as Ko-fi for payments). We are not responsible for their
                        privacy practices. We recommend reviewing their privacy policies before providing any information.
                    </p>

                    <h2>12. Children and Young People</h2>
                    <p>
                        Nina is designed for language learners of all ages, including minors. If you are under 16 (or the age of digital consent in your country):
                    </p>
                    <ul>
                        <li>We minimize data collection to only what is necessary</li>
                        <li>We do not use targeted advertising or tracking</li>
                        <li>For users under 16, parental/guardian consent may be required in some jurisdictions</li>
                        <li>We maintain heightened security standards for young users' data</li>
                    </ul>
                    <p>
                        Parents or guardians concerned about their child's data can contact us at privacy@nina-learn.de.
                    </p>

                    <h2>13. Data Breach Notification</h2>
                    <p>
                        In the event of a data breach that compromises your personal data, we will notify affected users and relevant authorities
                        as required by GDPR (typically within 72 hours of discovery) and provide information about the breach and recommended steps.
                    </p>

                    <h2>14. Updates to This Policy</h2>
                    <p>
                        We may update this Privacy Policy periodically to reflect changes in our practices or applicable law. We will notify you of
                        significant changes by posting the updated policy on our website with an updated "Last Updated" date. Your continued use of
                        the Services constitutes your acceptance of the updated policy.
                    </p>

                    <h2>15. Supervisory Authority</h2>
                    <p>
                        If you have concerns about how we handle your data, you have the right to lodge a complaint with your local data protection
                        authority (your country's Datenschutzbehörde or equivalent).
                    </p>

                    <p className="text-sm opacity-70 mt-8">
                        Last Updated: December 2025
                    </p>
                </div>
            </section>
        </>
    );
}
