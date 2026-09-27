package app.pocketport.companion

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RepoNormalizerTest {
    @Test
    fun ownerRepoBecomesGithubUrl() {
        assertEquals(
            "https://github.com/deepseek-ai/deepseek-harness",
            normalizeRepository("deepseek-ai/deepseek-harness"),
        )
    }

    @Test
    fun githubUrlIsNormalized() {
        assertEquals(
            "https://github.com/levomm/pocketport",
            normalizeRepository("https://github.com/levomm/pocketport.git"),
        )
    }

    @Test
    fun nonGithubUrlIsRejected() {
        assertNull(normalizeRepository("https://example.com/owner/repo"))
    }
}
